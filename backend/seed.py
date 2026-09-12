import asyncio
from datetime import datetime, timezone

from lib.db import db, ensure_indexes
from models.compliance import ScanRecord
from routers.compliance import fallback_declarations, DEMO_IMAGE


async def main() -> None:
    await ensure_indexes()
    if await db.scans.count_documents({}) > 0:
        print("scan seed already present")
        return
    samples = [
        ("Fortune Sunflower Oil 1L", "Adani Wilmar Ltd.", "Edible Oil", "Delhi NCR", "INS-042 · Aditi Rao", "compliant", 0, "not_required", ""),
        ("Shakti Premium Atta 5kg", "Shakti Foods Pvt. Ltd.", "Staples", "Maharashtra", "INS-017 · Rohan Mehta", "non_compliant", 2, "pending", "Verify the principal display panel font height before notice issue."),
        ("Natura Hand Wash 250ml", "Natura Consumer Products", "Personal Care", "Karnataka", "INS-031 · Neha Kapoor", "review", 0, "pending", "Consumer care address is partially obscured by the sticker."),
        ("Golden Harvest Basmati Rice", "Golden Harvest Foods", "Staples", "Tamil Nadu", "INS-024 · Vikram Singh", "non_compliant", 1, "verified", "MRP statement does not include inclusive tax language."),
        ("FreshDrop Mango Drink", "FreshDrop Beverages", "Beverages", "Delhi NCR", "INS-042 · Aditi Rao", "compliant", 0, "not_required", ""),
        ("HomeCare Detergent 2kg", "HomeCare Industries", "Household", "Gujarat", "INS-008 · Imran Khan", "non_compliant", 2, "pending", "Imported product address needs officer verification."),
    ]
    declarations = fallback_declarations()
    docs = []
    for index, (product, manufacturer, category, region, inspector, status, violations, review, remarks) in enumerate(samples):
        adjusted = [item.model_copy() for item in declarations]
        if status == "compliant":
            adjusted = [item.model_copy(update={"status": "compliant", "reason": "Declaration detected and meets the reference rule."}) for item in adjusted]
        elif status == "review":
            adjusted[4] = adjusted[4].model_copy(update={"status": "review"})
        else:
            adjusted[0] = adjusted[0].model_copy(update={"status": "non_compliant", "reason": "Address is missing the required PIN code."})
            adjusted[2] = adjusted[2].model_copy(update={"status": "non_compliant", "reason": "MRP statement needs inclusive tax wording."})
        record = ScanRecord(product_name=product, manufacturer=manufacturer, category=category, region=region, inspector=inspector, status=status, scanned_at=datetime(2024, 6, 20 - index, 10, 30, tzinfo=timezone.utc), image_url=DEMO_IMAGE, declarations=adjusted, violation_count=violations, review_status=review, remarks=remarks)
        docs.append(record.model_dump())
    await db.scans.insert_many(docs)
    print(f"seeded {len(docs)} scans")


if __name__ == "__main__":
    asyncio.run(main())