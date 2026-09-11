import re

def extract_fields(text):
    fields = {
        "mrp": None,
        "net_quantity": None,
        "date": None,
        "batch_number": None,
        "manufacturer": None
    }

    mrp_match = re.search(
        r"(?:MRP|M\.R\.P\.?)\s*(?:₹|Rs\.?|INR)?\s*([0-9]+(?:\.[0-9]{1,2})?)",
        text,
        re.IGNORECASE
    )

    quantity_match = re.search(
        r"\b([0-9]+(?:\.[0-9]+)?)\s*(kg|g|mg|l|ml)\b",
        text,
        re.IGNORECASE
    )

    date_match = re.search(
        r"\b([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})\b",
        text
    )

    batch_match = re.search(
        r"(?:Batch|Lot|LOT|BATCH)\s*(?:No\.?|Number)?\s*[:\-]?\s*([A-Za-z0-9\/\-]+)",
        text,
        re.IGNORECASE
    )

    if mrp_match:
        fields["mrp"] = mrp_match.group(1)

    if quantity_match:
        fields["net_quantity"] = quantity_match.group(0)

    if date_match:
        fields["date"] = date_match.group(1)

    if batch_match:
        fields["batch_number"] = batch_match.group(1)

    return fields