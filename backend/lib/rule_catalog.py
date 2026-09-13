import json
from pathlib import Path

from models.compliance import DeclarationResult, RuleEngineReport, RuleItem, RuleResult


CATALOG_PATH = Path(__file__).parent.parent / "official_rules_config.json"
CATALOG = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
RULES = [RuleItem(rule_code=f"Rule {item['rule_number']}", min_font_height_mm=1.0 if item["rule_number"] == "7" else 0, mandatory=item["rule_number"] in {"4", "6", "7", "8", "9", "10", "11", "12", "13"}, **item) for item in CATALOG["rules"]]

DECLARATION_RULES = {
    "6": ("manufacturer_details", "commodity_name", "net_quantity", "mrp", "date_mfg", "consumer_care"),
    "7": ("font_size_pdp",),
    "8": ("font_size_pdp", "net_quantity"),
    "9": ("font_size_pdp",),
    "10": ("manufacturer_details",),
    "11": ("net_quantity",),
    "12": ("net_quantity",),
    "13": ("net_quantity",),
}
MANUAL_RULES = {"5", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "25", "27", "28", "33"}
NOT_APPLICABLE_RULES = {"1", "2", "24", "29", "30", "31", "32", "34"}


def _status_from_declarations(items: list[DeclarationResult]) -> str:
    if any(item.status == "non_compliant" for item in items):
        return "non_compliant"
    if any(item.status == "manual_review" for item in items):
        return "manual_verification"
    if any(item.status in {"not_detected", "review"} for item in items):
        return "not_detected"
    if items and all(item.status == "compliant" for item in items):
        return "compliant"
    return "manual_verification"


def build_rule_results(declarations: list[DeclarationResult], engine_report: RuleEngineReport, category: str, quality_warnings: list[str]) -> list[RuleResult]:
    by_key = {item.key: item for item in declarations}
    results: list[RuleResult] = []
    for rule in RULES:
        number = rule.rule_number
        evidence_items = [by_key[key] for key in DECLARATION_RULES.get(number, ()) if key in by_key]
        status = "not_applicable"
        extracted = None
        confidence = "high"
        evidence_image_id = None
        evidence_face = None
        explanation = rule.inspector_explanation
        if number == "3":
            status = "not_applicable" if engine_report.out_of_scope else "compliant"
            explanation = engine_report.scope_reason or "The package is within the retail-package scope based on available evidence."
        elif number == "4":
            status = _status_from_declarations(list(by_key.values()))
            explanation = "The complete declaration set was evaluated across all uploaded package faces."
        elif number == "26":
            status = "not_applicable" if engine_report.exempt else "compliant"
            explanation = engine_report.exempt_reason or "No configured Rule 26 exemption was identified."
        elif evidence_items:
            status = _status_from_declarations(evidence_items)
            primary = next((item for item in evidence_items if item.status != "compliant"), evidence_items[0])
            extracted = primary.detected_value
            confidence = primary.confidence
            evidence_image_id = primary.evidence_image_id
            evidence_face = primary.evidence_face
            explanation = primary.reason
            if number == "9" and quality_warnings and status == "compliant":
                status = "manual_verification"
                confidence = "low"
                explanation = "Image-quality warnings prevent a reliable legibility/contrast decision: " + "; ".join(quality_warnings)
        elif number in MANUAL_RULES:
            status = "manual_verification"
            confidence = "low"
        elif number in NOT_APPLICABLE_RULES:
            status = "not_applicable"
        if number in {"14", "15", "16", "17"} and category not in {"Home Décor/Home Products", "Stationery"}:
            status = "not_applicable"
            explanation = "The detected category does not make this specialised dimensional rule applicable."
            confidence = "high"
        results.append(RuleResult(
            rule_id=rule.id,
            rule_number=number,
            rule_title=rule.title,
            requirement=rule.requirement,
            extracted_value=extracted,
            status=status,
            severity=rule.severity,
            confidence=confidence,
            evidence_image_id=evidence_image_id,
            evidence_face=evidence_face,
            explanation=explanation,
            consumer_explanation=rule.consumer_explanation,
            official_source=rule.official_source,
        ))
    return results