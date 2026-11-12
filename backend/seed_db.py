import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
db = client[os.getenv("MONGO_DB_NAME", "LedgerPilot")]
po_collection = db["PurchaseOrders"]
vendors_collection = db["Vendors"]

# 1. Wipe the old database clean
db["Invoices"].delete_many({})
po_collection.delete_many({})
vendors_collection.delete_many({})

# 2. Insert the updated $50 Purchase Order
mock_po = {
    "po_number": "PO-999888",
    "vendor_name": "TechFlow Solutions",
    "status": "open",
    "line_items": [
        {"description": "Software Development Services", "quantity": 1, "unit_price": 50.00}
    ],
}

mock_vendor = {
    "vendor_name": "TechFlow Solutions",
    "bank_account_details": "09876543210987",
    "paypal_email": os.getenv("PAYPAL_RECEIVER_EMAIL", ""),
}

po_collection.insert_one(mock_po)
vendors_collection.insert_one(mock_vendor)
db["Invoices"].create_index([("vendor_name", 1), ("invoice_number", 1)])
print("Database wiped! Mock Purchase Order ($50) and Vendor inserted.")