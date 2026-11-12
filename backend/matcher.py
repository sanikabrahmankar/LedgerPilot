import numpy as np
from scipy.optimize import linear_sum_assignment
from thefuzz import fuzz

from config import safe_float

MATCH_COST_THRESHOLD = 50
PRICE_TOLERANCE = 0.01
QUANTITY_TOLERANCE = 1e-9


def match_invoice_to_po(invoice_lines, po_lines):
    """
    Uses the Hungarian algorithm to optimally map invoice lines to PO lines,
    then reports per-line price and quantity variances.
    """
    invoice_lines = invoice_lines or []
    po_lines = po_lines or []
    num_inv = len(invoice_lines)
    num_po = len(po_lines)

    if num_inv == 0 or num_po == 0:
        return {
            "matches": [],
            "unmatched_invoice_lines": list(invoice_lines),
            "unmatched_po_lines": list(po_lines),
            "variances": [],
        }

    cost_matrix = np.zeros((num_inv, num_po))

    for i, inv_line in enumerate(invoice_lines):
        for j, po_line in enumerate(po_lines):
            text_sim = fuzz.token_sort_ratio(
                str(inv_line.get("description", "")).lower(),
                str(po_line.get("description", "")).lower(),
            )
            text_cost = 100 - text_sim
            price_diff = abs(
                safe_float(inv_line.get("unit_price")) - safe_float(po_line.get("unit_price"))
            )
            cost_matrix[i, j] = text_cost + (price_diff * 2)

    row_ind, col_ind = linear_sum_assignment(cost_matrix)

    matches = []
    variances = []
    matched_inv_indices = set()
    matched_po_indices = set()

    for r, c in zip(row_ind, col_ind):
        if cost_matrix[r, c] >= MATCH_COST_THRESHOLD:
            continue
        inv_line, po_line = invoice_lines[r], po_lines[c]
        matches.append(
            {
                "invoice_item": inv_line,
                "po_item": po_line,
                "match_confidence": round(float(100 - cost_matrix[r, c]), 2),
            }
        )
        matched_inv_indices.add(r)
        matched_po_indices.add(c)

        inv_price = safe_float(inv_line.get("unit_price"))
        po_price = safe_float(po_line.get("unit_price"))
        inv_qty = safe_float(inv_line.get("quantity"))
        po_qty = safe_float(po_line.get("quantity"))

        if inv_price - po_price > PRICE_TOLERANCE:
            variances.append(
                {
                    "description": str(inv_line.get("description", "")),
                    "type": "price",
                    "invoice_value": inv_price,
                    "po_value": po_price,
                }
            )
        if inv_qty - po_qty > QUANTITY_TOLERANCE:
            variances.append(
                {
                    "description": str(inv_line.get("description", "")),
                    "type": "quantity",
                    "invoice_value": inv_qty,
                    "po_value": po_qty,
                }
            )

    unmatched_inv_lines = [
        line for i, line in enumerate(invoice_lines) if i not in matched_inv_indices
    ]
    unmatched_po_lines = [
        line for j, line in enumerate(po_lines) if j not in matched_po_indices
    ]

    return {
        "matches": matches,
        "unmatched_invoice_lines": unmatched_inv_lines,
        "unmatched_po_lines": unmatched_po_lines,
        "variances": variances,
    }