import re
from dataclasses import dataclass


MRP_CONTEXT = re.compile(r"\b(?:mrp|m\.?r\.?p\.?|maximum\s+retail\s+price)\b", re.IGNORECASE)
PRICE = re.compile(r"(?:₹|rs\.?|inr)?\s*(\d{1,6}(?:[,.]\d{1,2})?)\s*(?:/-)?", re.IGNORECASE)
NEGATIVE_CONTEXT = re.compile(r"\b(?:sale|selling|offer|discount|unit\s*price|per\s*(?:g|kg|ml|l)|gst|tax|batch|lot|barcode|code|phone|mobile)\b", re.IGNORECASE)


@dataclass
class MrpMatch:
    value: str | None
    raw: str | None
    confidence: str
    score: float
    image_index: int | None


def detect_mrp(ocr_texts: list[str]) -> MrpMatch:
    candidates: list[tuple[float, float, str, int]] = []
    for image_index, text in enumerate(ocr_texts):
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for index, line in enumerate(lines):
            context = " ".join(lines[max(0, index - 1): min(len(lines), index + 2)])
            has_mrp = bool(MRP_CONTEXT.search(context))
            for match in PRICE.finditer(line):
                raw_number = match.group(1).replace(",", "")
                try:
                    amount = float(raw_number)
                except ValueError:
                    continue
                if amount <= 0 or amount > 1_000_000:
                    continue
                score = 0.15
                if has_mrp:
                    score += 0.62
                if re.search(r"maximum\s+retail\s+price", context, re.IGNORECASE):
                    score += 0.12
                if re.search(r"incl\.?\s*(?:of)?\s*all\s*taxes", context, re.IGNORECASE):
                    score += 0.08
                if re.search(r"₹|rs\.?|inr", line, re.IGNORECASE):
                    score += 0.08
                if NEGATIVE_CONTEXT.search(context) and not has_mrp:
                    score -= 0.5
                if re.search(r"\b\d{8,}\b", line):
                    score -= 0.5
                candidates.append((score, amount, line, image_index))
    if not candidates:
        return MrpMatch(None, None, "low", 0, None)
    score, amount, raw, image_index = max(candidates, key=lambda item: item[0])
    confidence = "high" if score >= 0.78 else "medium" if score >= 0.58 else "low"
    value = f"₹{amount:.2f}" if confidence != "low" else None
    return MrpMatch(value, raw, confidence, round(score, 2), image_index)