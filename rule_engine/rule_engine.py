"""
LMPC Compliance Rule Engine (v2)
--------------------------------
Config-driven engine for checking extracted label data against the
Legal Metrology (Packaged Commodities) Rules, 2011.

Pipeline per product:
  1. Scope check   (Rule 3)  -- is this product covered by Chapter II at all?
  2. Exemption check (Rule 26, Rule 6 provisos) -- fully or partially exempt?
  3. Mandatory declaration checks (Rule 6)
  4. Font/placement checks (Rule 7, 8, 9)
  5. Language check (Rule 9(4))

Expected input `data` dict (produced by the OCR/NLP layer) -- see the
`sample_extracted_data` block at the bottom and INPUT_SCHEMA.md for the
full contract to agree with the OCR/AI teammate.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Violation:
    rule_id: str
    rule_ref: str
    severity: str  # critical | major | minor | info
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


# ---------------------------------------------------------------------------
# Safe boolean condition parser
# ---------------------------------------------------------------------------
# Supports: field == 'value', field != 'value', field > N, field < N,
# combined with 'and' / 'or' (left-to-right, no operator precedence --
# use parentheses-free simple conditions only, which is all the config uses).
# This intentionally avoids eval() on user/config-controlled strings.

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

    # Split on top-level ' and ' / ' or ' (case sensitive keywords in config).
    # No nested parens supported -- keep config conditions flat.
    parts = re.split(r"\s+(and|or)\s+", condition.strip())
    results = []
    ops = []
    for i, part in enumerate(parts):
        if part in ("and", "or"):
            ops.append(part)
            continue
        m = _COND_TOKEN.match(part.strip())
        if not m:
            raise ValueError(f"Unparseable condition clause: '{part}'")
        f, op, raw_val = m.group("field"), m.group("op"), m.group("value")
        actual = data.get(f)
        expected = _coerce(raw_val)
        if isinstance(expected, str) and actual is not None:
            actual_cmp = str(actual)
        else:
            actual_cmp = actual
        result = {
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
            ">": lambda a, b: (a is not None) and a > b,
            "<": lambda a, b: (a is not None) and a < b,
            ">=": lambda a, b: (a is not None) and a >= b,
            "<=": lambda a, b: (a is not None) and a <= b,
        }[op](actual_cmp, expected)
        results.append(result)

    out = results[0]
    for op, val in zip(ops, results[1:]):
        out = (out and val) if op == "and" else (out or val)
    return out


# ---------------------------------------------------------------------------
# Rule engine
# ---------------------------------------------------------------------------

class RuleEngine:
    def __init__(self, config_path: str):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

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

        # 1. Scope check -- if out of scope, stop entirely.
        for rule in self.config.get("scope_exclusions", []):
            if eval_condition(rule["condition"], data):
                report.out_of_scope = True
                report.scope_reason = f"[{rule['rule_ref']}] {rule['message']}"
                return report

        # 2. Exemption checks -- full or per-field.
        exempt_fields = set()
        for rule in self.config.get("exemptions", []):
            check_type = rule["check_type"]
            if check_type == "exempt_if" and eval_condition(rule["condition"], data):
                report.exempt = True
                report.exempt_reason = f"[{rule['rule_ref']}] {rule['message']}"
                return report
            if check_type == "exempt_field_if" and eval_condition(rule["condition"], data):
                exempt_fields.add(rule["field"])

        # 3. Mandatory declarations (skip fields that are individually exempt).
        for rule in self.config.get("mandatory_declarations", []):
            if rule.get("field") in exempt_fields:
                continue
            self._run_rule(rule, data, report)

        # 4. Font & placement.
        for rule in self.config.get("font_and_placement_rules", []):
            self._run_rule(rule, data, report)

        # 5. Language.
        lang_rule = self.config.get("language_rule")
        if lang_rule:
            self._run_rule(lang_rule, data, report)

        return report

    # ---- dispatch -------------------------------------------------------

    def _run_rule(self, rule: dict, data: dict, report: ComplianceReport):
        condition = rule.get("required_if")
        if condition and not eval_condition(condition, data):
            return

        check_type = rule.get("check_type")
        validator = self.validators.get(check_type)
        if validator is None:
            report.violations.append(
                Violation(rule["id"], rule.get("rule_ref", ""), "info",
                          f"No validator implemented for check_type '{check_type}'")
            )
            return

        ok, msg = validator(rule, data)
        if ok:
            report.passed_checks.append(rule["id"])
        else:
            report.violations.append(
                Violation(
                    rule_id=rule["id"],
                    rule_ref=rule.get("rule_ref", ""),
                    severity=rule.get("severity", "minor"),
                    message=msg or rule.get("message", "Compliance check failed."),
                    field=rule.get("field"),
                )
            )

    # ---- validators -------------------------------------------------------

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
        hits = [w for w in rule["forbidden"] if w in value]
        if hits:
            return (False, f"Contains misleading qualifier(s): {', '.join(hits)}")
        return (True, None)

    @staticmethod
    def _check_date_format(rule, data):
        raw = data.get(rule["field"])
        if not raw:
            return (False, None)
        for fmt in ["%m/%Y", "%b %Y", "%m-%Y", "%B %Y"]:
            try:
                datetime.strptime(str(raw), fmt)
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
        is_embossed = data.get("is_embossed", False)
        min_required = rule["molded_or_embossed_min_mm"] if is_embossed else rule["normal_min_mm"]
        failing = [f for f, h in heights.items() if h < min_required]
        if failing:
            return (False, f"Fields below {min_required}mm minimum: {', '.join(failing)}")
        return (True, None)

    @staticmethod
    def _check_tiered_lookup(rule, data):
        # Only run the table that matches this product's quantity_type,
        # so Table-I and Table-II don't both fire on the same product.
        if data.get("quantity_type") != rule["quantity_type"]:
            return (True, None)  # not applicable -> not a violation

        qty = data.get(rule["lookup_field"])
        heights = data.get("font_heights_mm", {})
        if qty is None:
            return (False, f"'{rule['lookup_field']}' not available for tiered font check.")

        for tier in rule["table"]:
            lo, hi = tier["min"], tier["max"]
            if qty >= lo and (hi is None or qty < hi):
                is_embossed = data.get("is_embossed", False)
                min_required = tier["embossed_min_mm"] if is_embossed else tier["normal_min_mm"]
                failing = []
                for applies_field in rule["applies_to"]:
                    h = heights.get(applies_field)
                    if h is not None and h < min_required:
                        failing.append(f"{applies_field} ({h}mm < {min_required}mm)")
                if failing:
                    return (False, f"Below required height for this band: {', '.join(failing)}")
                return (True, None)
        return (False, "Quantity value did not match any table band -- check table config.")

    @staticmethod
    def _check_ratio(rule, data):
        ratios = data.get("letter_width_height_ratios", {})
        min_ratio = rule["min_width_to_height_ratio"]
        failing = [k for k, r in ratios.items() if r < min_ratio]
        return (len(failing) == 0, f"Ratio below minimum for: {', '.join(failing)}" if failing else None)

    @staticmethod
    def _check_region_membership(rule, data):
        """
        Rule 8(1): every declaration must sit within the Principal Display
        Panel. Expects:
          data["pdp_box"] = {"x0":..,"y0":..,"x1":..,"y1":..}
          data["declaration_boxes"] = {"mrp": {...}, "net_quantity": {...}, ...}
        Box coordinates must be in the same unit (e.g. mm on the flattened
        label image) for both.
        """
        pdp = data.get("pdp_box")
        boxes = data.get("declaration_boxes")
        if not pdp or not boxes:
            return (True, None)  # geometry not available yet -- don't fail the run

        def inside(box, container):
            return (box["x0"] >= container["x0"] and box["y0"] >= container["y0"]
                    and box["x1"] <= container["x1"] and box["y1"] <= container["y1"])

        outside = [name for name, box in boxes.items() if not inside(box, pdp)]
        if outside:
            return (False, f"Declarations outside PDP: {', '.join(outside)}")
        return (True, None)

    @staticmethod
    def _check_free_zone_margin(rule, data):
        """
        Rule 8(1) proviso: area around the net-quantity declaration must be
        clear of other print by >=1x numeral height (top/bottom) and >=2x
        numeral height (left/right). Expects:
          data["net_quantity_box"] = {x0,y0,x1,y1}
          data["nearest_other_text_distance_mm"] = {"top":.., "bottom":.., "left":.., "right":..}
          data["font_heights_mm"]["net_quantity"]
        """
        h = data.get("font_heights_mm", {}).get(rule["field"])
        distances = data.get("nearest_other_text_distance_mm")
        if h is None or not distances:
            return (True, None)  # geometry not available -- don't fail the run

        tb_required = h * rule["min_top_bottom_margin_ratio"]
        lr_required = h * rule["min_left_right_margin_ratio"]
        problems = []
        if distances.get("top", 0) < tb_required:
            problems.append("top")
        if distances.get("bottom", 0) < tb_required:
            problems.append("bottom")
        if distances.get("left", 0) < lr_required:
            problems.append("left")
        if distances.get("right", 0) < lr_required:
            problems.append("right")
        if problems:
            return (False, f"Insufficient clear space around net quantity on: {', '.join(problems)}")
        return (True, None)

    @staticmethod
    def _check_relative_emphasis(rule, data):
        """
        Rule 9(1)(b): MRP/net quantity numerals must contrast with the
        background and be at least as prominent as body text. Expects:
          data["font_heights_mm"][field] and data["body_text_height_mm"]
          data["contrast_ok"][field] -> bool (from your CV contrast-ratio calc)
        """
        body_height = data.get("body_text_height_mm")
        heights = data.get("font_heights_mm", {})
        contrast = data.get("contrast_ok", {})
        if body_height is None:
            return (True, None)  # geometry not available -- don't fail the run

        problems = []
        for f in rule["fields"]:
            h = heights.get(f)
            if h is not None and h < body_height * rule["must_meet_or_exceed_body_ratio"]:
                problems.append(f"{f} not larger than body text")
            if rule.get("must_contrast_with_background") and contrast.get(f) is False:
                problems.append(f"{f} lacks contrast with background")
        if problems:
            return (False, "; ".join(problems))
        return (True, None)

    @staticmethod
    def _check_language(rule, data):
        detected = data.get("detected_language", "en")
        return (detected in rule["allowed_languages"], None)


# ---------------------------------------------------------------------------
# Example run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sample_extracted_data = {
        "manufacturer_address": "ABC Foods Pvt Ltd, Sector 5, Noida, UP",
        "commodity_name": "Wheat Flour",
        "net_quantity": "500 g",
        "net_quantity_value_g_ml": 500,
        "quantity_type": "weight_or_volume",
        "mrp": "Rs.55 (incl. of all taxes)",
        "mfg_date": "08/2026",
        "consumer_care": "care@abcfoods.com",
        "is_imported": False,
        "buyer_type": "retail",
        "category": "packaged_food",
        "font_heights_mm": {"mrp": 4.5, "net_quantity": 4.2, "commodity_name": 1.2},
        "is_embossed": False,
        "letter_width_height_ratios": {"mrp": 0.4, "net_quantity": 0.35},
        "detected_language": "en",
        # Geometry fields left out on purpose -> those checks pass through as N/A
        # until the CV pipeline supplies them.
    }

    engine = RuleEngine("lmpc_rules_config.json")
    report = engine.evaluate(product_id="SKU-001", data=sample_extracted_data)
    print(json.dumps(report.to_dict(), indent=2))
