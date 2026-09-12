"""
LMPC Compliance Rule Engine (v2)
--------------------------------
Config-driven engine for checking extracted label data against the
Legal Metrology (Packaged Commodities) Rules, 2011.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class Violation:
    rule_id: str
    rule_ref: str
    severity: str
    message: str
    field: Optional[str] = None


@dataclass
class ComplianceReport:
    product_id: str
    violations: list = field(default_factory=list)
    passed_checks: list = field(default_factory=list)
    exempt: bool = False
    exempt_reason: Optional[str] = None
    out_of_scope: bool = False
    scope_reason: Optional[str] = None

    @property
    def is_compliant(self) -> bool:
        return len(self.violations) == 0

    @property
    def critical_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "critical")

    def to_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "out_of_scope": self.out_of_scope,
            "scope_reason": self.scope_reason,
            "exempt": self.exempt,
            "exempt_reason": self.exempt_reason,
            "is_compliant": self.is_compliant,
            "critical_violations": self.critical_count,
            "total_violations": len(self.violations),
            "violations": [v.__dict__ for v in self.violations],
            "passed_checks": self.passed_checks,
        }


_COND_TOKEN = re.compile(
    r"""(?P<field>[\w.]+)\s*
        (?P<op>==|!=|>=|<=|>|<)\s*
        (?P<value>'[^']*'|"[^"]*"|[-\w.]+)""",
    re.VERBOSE,
)


def _coerce(raw: str):
    raw = raw.strip()
    if (raw.startswith("'") and raw.endswith("'")) or (raw.startswith('"') and raw.endswith('"')):
        return raw[1:-1]
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    try:
        return float(raw) if "." in raw else int(raw)
    except ValueError:
        return raw


def eval_condition(condition: str, data: dict) -> bool:
    """Evaluate a simple 'and'/'or'-joined condition string against data."""
    if not condition:
        return True
    parts = re.split(r"\s+(and|or)\s+", condition.strip())
    results = []
    ops = []
    for part in parts:
        if part in ("and", "or"):
            ops.append(part)
            continue
        match = _COND_TOKEN.match(part.strip())
        if not match:
            raise ValueError(f"Unparseable condition clause: '{part}'")
        field_name, operator, raw_value = match.group("field"), match.group("op"), match.group("value")
        actual = data.get(field_name)
        expected = _coerce(raw_value)
        actual_cmp = str(actual) if isinstance(expected, str) and actual is not None else actual
        result = {
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
            ">": lambda a, b: (a is not None) and a > b,
            "<": lambda a, b: (a is not None) and a < b,
            ">=": lambda a, b: (a is not None) and a >= b,
            "<=": lambda a, b: (a is not None) and a <= b,
        }[operator](actual_cmp, expected)
        results.append(result)
    out = results[0]
    for operator, value in zip(ops, results[1:]):
        out = (out and value) if operator == "and" else (out or value)
    return out


class RuleEngine:
    def __init__(self, config_path: str):
        with open(config_path, "r", encoding="utf-8") as file:
            self.config = json.load(file)
        self.validators = {
            "presence": self._check_presence,
            "regex": self._check_regex,
            "forbidden_words": self._check_forbidden_words,
            "date_format": self._check_date_format,
            "presence_with_contact": self._check_contact,
            "min_height_mm": self._check_min_height,
            "tiered_lookup": self._check_tiered_lookup,
            "ratio": self._check_ratio,
            "region_membership": self._check_region_membership,
            "free_zone_margin": self._check_free_zone_margin,
            "relative_font_emphasis": self._check_relative_emphasis,
            "language_detect": self._check_language,
        }

    def evaluate(self, product_id: str, data: dict) -> ComplianceReport:
        report = ComplianceReport(product_id=product_id)
        for rule in self.config.get("scope_exclusions", []):
            if eval_condition(rule["condition"], data):
                report.out_of_scope = True
                report.scope_reason = f"[{rule['rule_ref']}] {rule['message']}"
                return report
        exempt_fields = set()
        for rule in self.config.get("exemptions", []):
            check_type = rule["check_type"]
            if check_type == "exempt_if" and eval_condition(rule["condition"], data):
                report.exempt = True
                report.exempt_reason = f"[{rule['rule_ref']}] {rule['message']}"
                return report
            if check_type == "exempt_field_if" and eval_condition(rule["condition"], data):
                exempt_fields.add(rule["field"])
        for rule in self.config.get("mandatory_declarations", []):
            if rule.get("field") not in exempt_fields:
                self._run_rule(rule, data, report)
        for rule in self.config.get("font_and_placement_rules", []):
            self._run_rule(rule, data, report)
        language_rule = self.config.get("language_rule")
        if language_rule:
            self._run_rule(language_rule, data, report)
        return report

    def _run_rule(self, rule: dict, data: dict, report: ComplianceReport):
        condition = rule.get("required_if")
        if condition and not eval_condition(condition, data):
            return
        check_type = rule.get("check_type")
        validator = self.validators.get(check_type)
        if validator is None:
            report.violations.append(Violation(rule["id"], rule.get("rule_ref", ""), "info", f"No validator implemented for check_type '{check_type}'"))
            return
        ok, message = validator(rule, data)
        if ok:
            report.passed_checks.append(rule["id"])
        else:
            report.violations.append(Violation(rule_id=rule["id"], rule_ref=rule.get("rule_ref", ""), severity=rule.get("severity", "minor"), message=message or rule.get("message", "Compliance check failed."), field=rule.get("field")))

    @staticmethod
    def _check_presence(rule, data):
        return (bool(data.get(rule["field"])), None)

    @staticmethod
    def _check_regex(rule, data):
        value = str(data.get(rule["field"], "") or "")
        flags = re.IGNORECASE if rule.get("case_insensitive") else 0
        return (bool(re.match(rule["pattern"], value.strip(), flags)), None)

    @staticmethod
    def _check_forbidden_words(rule, data):
        value = str(data.get(rule["field"], "") or "").lower()
        hits = [word for word in rule["forbidden"] if word in value]
        return (False, f"Contains misleading qualifier(s): {', '.join(hits)}") if hits else (True, None)

    @staticmethod
    def _check_date_format(rule, data):
        raw = data.get(rule["field"])
        if not raw:
            return (False, None)
        for date_format in ["%m/%Y", "%b %Y", "%m-%Y", "%B %Y"]:
            try:
                datetime.strptime(str(raw), date_format)
                return (True, None)
            except ValueError:
                continue
        return (False, f"Date '{raw}' does not match an accepted MM/YYYY format.")

    @staticmethod
    def _check_contact(rule, data):
        value = data.get(rule["field"])
        if not value:
            return (False, None)
        has_phone = bool(re.search(r"\+?\d[\d\-\s]{7,}", str(value)))
        has_email = bool(re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", str(value)))
        return (has_phone or has_email, None)

    @staticmethod
    def _check_min_height(rule, data):
        heights = data.get("font_heights_mm", {})
        minimum = rule["molded_or_embossed_min_mm"] if data.get("is_embossed", False) else rule["normal_min_mm"]
        failing = [field_name for field_name, height in heights.items() if height < minimum]
        return (False, f"Fields below {minimum}mm minimum: {', '.join(failing)}") if failing else (True, None)

    @staticmethod
    def _check_tiered_lookup(rule, data):
        if data.get("quantity_type") != rule["quantity_type"]:
            return (True, None)
        quantity = data.get(rule["lookup_field"])
        heights = data.get("font_heights_mm", {})
        if quantity is None:
            return (False, f"'{rule['lookup_field']}' not available for tiered font check.")
        for tier in rule["table"]:
            if quantity >= tier["min"] and (tier["max"] is None or quantity < tier["max"]):
                minimum = tier["embossed_min_mm"] if data.get("is_embossed", False) else tier["normal_min_mm"]
                failing = []
                for field_name in rule["applies_to"]:
                    height = heights.get(field_name)
                    if height is not None and height < minimum:
                        failing.append(f"{field_name} ({height}mm < {minimum}mm)")
                return (False, f"Below required height for this band: {', '.join(failing)}") if failing else (True, None)
        return (False, "Quantity value did not match any table band -- check table config.")

    @staticmethod
    def _check_ratio(rule, data):
        failing = [key for key, ratio in data.get("letter_width_height_ratios", {}).items() if ratio < rule["min_width_to_height_ratio"]]
        return (len(failing) == 0, f"Ratio below minimum for: {', '.join(failing)}" if failing else None)

    @staticmethod
    def _check_region_membership(rule, data):
        pdp = data.get("pdp_box")
        boxes = data.get("declaration_boxes")
        if not pdp or not boxes:
            return (True, None)
        def inside(box, container):
            return box["x0"] >= container["x0"] and box["y0"] >= container["y0"] and box["x1"] <= container["x1"] and box["y1"] <= container["y1"]
        outside = [name for name, box in boxes.items() if not inside(box, pdp)]
        return (False, f"Declarations outside PDP: {', '.join(outside)}") if outside else (True, None)

    @staticmethod
    def _check_free_zone_margin(rule, data):
        height = data.get("font_heights_mm", {}).get(rule["field"])
        distances = data.get("nearest_other_text_distance_mm")
        if height is None or not distances:
            return (True, None)
        top_bottom = height * rule["min_top_bottom_margin_ratio"]
        left_right = height * rule["min_left_right_margin_ratio"]
        problems = []
        if distances.get("top", 0) < top_bottom: problems.append("top")
        if distances.get("bottom", 0) < top_bottom: problems.append("bottom")
        if distances.get("left", 0) < left_right: problems.append("left")
        if distances.get("right", 0) < left_right: problems.append("right")
        return (False, f"Insufficient clear space around net quantity on: {', '.join(problems)}") if problems else (True, None)

    @staticmethod
    def _check_relative_emphasis(rule, data):
        body_height = data.get("body_text_height_mm")
        if body_height is None:
            return (True, None)
        heights = data.get("font_heights_mm", {})
        contrast = data.get("contrast_ok", {})
        problems = []
        for field_name in rule["fields"]:
            height = heights.get(field_name)
            if height is not None and height < body_height * rule["must_meet_or_exceed_body_ratio"]:
                problems.append(f"{field_name} not larger than body text")
            if rule.get("must_contrast_with_background") and contrast.get(field_name) is False:
                problems.append(f"{field_name} lacks contrast with background")
        return (False, "; ".join(problems)) if problems else (True, None)

    @staticmethod
    def _check_language(rule, data):
        return (data.get("detected_language", "en") in rule["allowed_languages"], None)