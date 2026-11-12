import json
import os
import re

from dotenv import load_dotenv

load_dotenv()


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


USE_MOCK_AI = env_bool("USE_MOCK_AI", False)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
GEMINI_TIMEOUT_SECONDS = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "60"))

# Risk policy ("mandate"): invoices at or above this score always need a human.
AUTO_APPROVE_RISK_THRESHOLD = int(os.getenv("AUTO_APPROVE_RISK_THRESHOLD", "20"))
# Invoices above this amount always need a human, regardless of risk score.
AUTO_PAY_MAX_AMOUNT = float(os.getenv("AUTO_PAY_MAX_AMOUNT", "5000"))

_model = None


def get_gemini_model():
    """Lazily build the Gemini client so mock mode never needs a key or network."""
    global _model
    if _model is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set (or set USE_MOCK_AI=true).")
        import google.generativeai as genai

        genai.configure(api_key=GEMINI_API_KEY)
        _model = genai.GenerativeModel(GEMINI_MODEL)
    return _model


def generate_json(contents):
    """Calls Gemini and returns the parsed JSON object from the response."""
    response = get_gemini_model().generate_content(
        contents,
        generation_config={"response_mime_type": "application/json"},
        request_options={"timeout": GEMINI_TIMEOUT_SECONDS},
    )
    return parse_json_text(response.text)


def parse_json_text(text):
    """Parses JSON even if the model wrapped it in markdown fences."""
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    return json.loads(cleaned)


def safe_float(value, default=0.0):
    """Coerces LLM output such as '$1,200.50' or None into a float."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(re.sub(r"[^\d.\-]", "", str(value)))
    except ValueError:
        return default