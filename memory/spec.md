# Legal Metrology Compliance Checker

## Purpose
Responsive enforcement prototype for Department of Consumer Affairs officials to inspect packaged commodity labels against the Legal Metrology (Packaged Commodities) Rules, 2011.

## Roles
- Field Inspector: scan/upload labels, view OCR findings, add remarks, open reports.
- Compliance Reviewer: review flagged findings, verify records, view analytics and repository.
- Admin Officer: access analytics, repository, user/role management, and editable rules reference.

## Data model
- ScanRecord: product, manufacturer, category, region, inspector, scanned_at, image_url, declarations, status, violation_count, review_status, remarks, and the complete rule_engine_report audit result.
- DeclarationResult: key, field_name, detected_value, status, rule_code, requirement, reason, font_size_mm, bbox.
- RuleItem: declaration requirement, legal rule code, minimum font height, mandatory flag, updated date.

## Key flows
1. Demo role selector enters the shell with tailored navigation.
2. Inspector opens Scan New Product, uploads or selects Demo scan, sees OCR processing, annotated result boxes, and declaration detail cards.
3. Reviewer/Admin can open Repository, Analytics, Rules, and User Management.
4. Report preview exposes remarks and downloadable mock PDF/DOCX files.

## Authentication
No real authentication in this hackathon prototype. Role selector simulates a clearly labeled active session.

## OCR integration
POST /api/compliance/scans calls Gemini `gemini-3.1-pro-preview` through `EMERGENT_LLM_KEY` when an image is supplied. If unavailable or response parsing fails, deterministic mock extraction keeps the demo flow working.

## Rule engine
All new scans pass the OCR/fallback extraction through the supplied `RuleEngine` in `backend/rule_engine.py`, configured by `backend/lmpc_rules_config.json` (`2017-amendment`). The adapter in `backend/lib/rule_adapter.py` normalizes OCR values to the supplied input contract and maps the engine's violations/passed checks back into the existing declaration cards. Gemini-provided compliance statuses and reasons are not used as final verdicts.