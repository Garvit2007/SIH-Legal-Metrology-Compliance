import re
from pathlib import Path

from models.compliance import DeclarationResult, RuleEngineReport
from rule_engine import RuleEngine


CONFIG_PATH = Path(__file__).parent.parent / "lmpc_rules_config.json"
ENGINE = RuleEngine(str(CONFIG_PATH))
RULE_VERSION = str(ENGINE.config.get("meta", {}).get("rule_version", "unknown"))

FIELD_TO_DECLARATION = {
    "manufacturer_address": "manufacturer_details",
    "net_quantity": "net_quantity",
    "mrp": "mrp",
    "mfg_date": "date_mfg",
    "consumer_care": "consumer_care",
}

RULE_TARGETS: dict[str, tuple[str, ...]] = {
    "MFR_ADDRESS": ("manufacturer_details",),
    "COMMODITY_NAME": ("manufacturer_details",),
    "NET_QUANTITY": ("net_quantity",),
    "NET_QUANTITY_NO_VAGUE_WORDS": ("net_quantity",),
    "MFG_DATE": ("date_mfg",),
    "MRP": ("mrp",),
    "CONSUMER_CARE": ("consumer_care",),
    "COUNTRY_OF_ORIGIN": ("manufacturer_details",),
    "DIMENSIONS_IF_RELEVANT": ("manufacturer_details",),
    "MIN_LETTER_HEIGHT": ("font_size_pdp",),
    "LETTER_WIDTH_RATIO": ("font_size_pdp",),
    "NUMERAL_HEIGHT_TABLE_I_WEIGHT_VOLUME": ("font_size_pdp",),
    "NUMERAL_HEIGHT_TABLE_II_LENGTH_AREA_NUMBER": ("font_size_pdp",),
    "PDP_PLACEMENT": ("font_size_pdp",),
    "QUANTITY_FREE_ZONE": ("net_quantity",),
    "MRP_PROMINENCE": ("mrp",),
    "LANGUAGE_HINDI_ENGLISH": ("font_size_pdp",),
}

CATEGORY_MAP = {
    "food & grocery": "packaged_food",
    "staples": "packaged_food",
    "edible oil": "packaged_food",
    "beverages": "packaged_food",
    "personal care": "packaged_food",
    "household": "packaged_food",
}


def _value(declarations: dict[str, DeclarationResult], key: str) -> str:
    return str(declarations.get(key).detected_value or "") if declarations.get(key) else ""


def _normalise_net_quantity(raw: str) -> tuple[str, float | None, str]:
    cleaned = re.sub(r"^\s*net\s*(qty\.?|quantity)\s*[:.-]?\s*", "", raw, flags=re.IGNORECASE).strip()
    match = re.search(r"(\d+(?:\.\d+)?)\s*(kg|mg|g|ml|l|N|U)\b", cleaned, flags=re.IGNORECASE)
    if not match:
        return cleaned, None, "weight_or_volume"
    amount = float(match.group(1))
    unit = match.group(2)
    lower_unit = unit.lower()
    if lower_unit == "kg":
        amount *= 1000
    elif lower_unit == "mg":
        amount /= 1000
    elif lower_unit == "l":
        amount *= 1000
    quantity_type = "length_area_or_number" if unit in {"N", "U"} else "weight_or_volume"
    return cleaned, amount, quantity_type


def _normalise_mrp(raw: str) -> str:
    return re.sub(r"^\s*MRP\s*[:.-]?\s*", "", raw, flags=re.IGNORECASE).strip()


def _normalise_date(raw: str) -> str:
    return re.sub(r"^\s*(packed\s+on|mfg\.?\s*date|manufactured\s+on)\s*[:.-]?\s*", "", raw, flags=re.IGNORECASE).strip()


def build_rule_input(product_name: str, category: str, declarations: list[DeclarationResult]) -> dict:
    by_key = {item.key: item for item in declarations}
    net_quantity, quantity_value, quantity_type = _normalise_net_quantity(_value(by_key, "net_quantity"))
    heights = {item.key: item.font_size_mm for item in declarations if item.font_size_mm is not None}
    boxes = {
        item.key: {
            "x0": item.bbox.x,
            "y0": item.bbox.y,
            "x1": item.bbox.x + item.bbox.width,
            "y1": item.bbox.y + item.bbox.height,
        }
        for item in declarations
    }
    return {
        "manufacturer_address": _value(by_key, "manufacturer_details"),
        "commodity_name": product_name,
        "net_quantity": net_quantity,
        "net_quantity_value_g_ml": quantity_value,
        "quantity_type": quantity_type,
        "mrp": _normalise_mrp(_value(by_key, "mrp")),
        "mfg_date": _normalise_date(_value(by_key, "date_mfg")),
        "consumer_care": _value(by_key, "consumer_care"),
        "is_imported": False,
        "buyer_type": "retail",
        "category": CATEGORY_MAP.get(category.lower(), category if category in CATEGORY_MAP.values() else "packaged_food"),
        "font_heights_mm": heights,
        "is_embossed": False,
        "letter_width_height_ratios": {},
        "detected_language": "en",
        "pdp_box": {"x0": 0, "y0": 0, "x1": 100, "y1": 100},
        "declaration_boxes": boxes,
    }


def apply_rule_engine(product_id: str, product_name: str, category: str, declarations: list[DeclarationResult]) -> tuple[list[DeclarationResult], RuleEngineReport]:
    engine_report = ENGINE.evaluate(product_id, build_rule_input(product_name, category, declarations))
    raw_report = engine_report.to_dict()
    summary = RuleEngineReport(rule_version=RULE_VERSION, **raw_report)
    if summary.out_of_scope or summary.exempt:
        reason = summary.scope_reason or summary.exempt_reason or "The configured engine marked this product as not applicable."
        return [item.model_copy(update={"status": "compliant", "reason": reason}) for item in declarations], summary

    violations_by_key: dict[str, list] = {item.key: [] for item in declarations}
    for violation in summary.violations:
        targets = RULE_TARGETS.get(violation.rule_id)
        if not targets and violation.field:
            mapped = FIELD_TO_DECLARATION.get(violation.field)
            targets = (mapped,) if mapped else ()
        for target in targets or ("font_size_pdp",):
            violations_by_key.setdefault(target, []).append(violation)

    checked_by_key: dict[str, list[str]] = {item.key: [] for item in declarations}
    for check_id in summary.passed_checks:
        for target in RULE_TARGETS.get(check_id, ()):
            checked_by_key.setdefault(target, []).append(check_id)

    evaluated: list[DeclarationResult] = []
    for item in declarations:
        violations = violations_by_key.get(item.key, [])
        if violations:
            references = " / ".join(dict.fromkeys(violation.rule_ref for violation in violations if violation.rule_ref))
            reason = "Rule engine: " + "; ".join(violation.message for violation in violations)
            evaluated.append(item.model_copy(update={"status": "non_compliant", "reason": reason, "rule_code": references or item.rule_code}))
        else:
            passed = checked_by_key.get(item.key, [])
            reason = f"Rule engine passed: {', '.join(passed)}." if passed else "No violation returned by the configured rule engine."
            evaluated.append(item.model_copy(update={"status": "compliant", "reason": reason}))
    return evaluated, summary