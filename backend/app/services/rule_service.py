from pathlib import Path

from app.rule_engine.rule_engine import RuleEngine


# Get the folder where this file is located
BASE_DIR = Path(__file__).resolve().parent.parent / "rule_engine"

# Load the Rule Engine configuration
CONFIG_PATH = BASE_DIR / "lmpc_rules_config.json"

# Create one Rule Engine instance
engine = RuleEngine(str(CONFIG_PATH))


def check_compliance(product_id, structured_json):
    """
    Send the structured OCR data to the Rule Engine
    and return the compliance report as a dictionary.
    """

    report = engine.evaluate(
        product_id=product_id,
        data=structured_json
    )

    return report.to_dict()