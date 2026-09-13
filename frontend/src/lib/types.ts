export type UserRole = "admin" | "inspector" | "consumer";
export type Confidence = "high" | "medium" | "low";
export type ComplianceStatus = "compliant" | "partially_compliant" | "non_compliant" | "manual_review" | "review";
export type DeclarationStatus = "compliant" | "non_compliant" | "not_detected" | "not_applicable" | "manual_review" | "review";
export type RuleResultStatus = "compliant" | "non_compliant" | "not_detected" | "not_applicable" | "manual_verification";
export type ReviewStatus = "not_required" | "pending" | "verified";

export interface User { id: string; email: string; name: string; role: UserRole; region: string; active: boolean }
export interface BoundingBox { x: number; y: number; width: number; height: number }
export interface ImageQuality { width: number; height: number; blur_score: number; brightness: number; glare_ratio: number; warnings: string[]; suitable: boolean }
export interface ScanImage { id: string; inspection_id: string; face_label: string; file_name: string; mime_type: string; data_url: string; sha256: string; quality: ImageQuality }
export interface DeclarationResult { key: string; field_name: string; detected_value: string | null; status: DeclarationStatus; confidence: Confidence; rule_code: string; requirement: string; reason: string; consumer_explanation: string; font_size_mm: number | null; bbox: BoundingBox; evidence_image_id: string | null; evidence_face: string | null }
export interface RuleEngineViolation { rule_id: string; rule_ref: string; severity: string; message: string; field: string | null }
export interface RuleEngineReport { product_id: string; rule_version: string; out_of_scope: boolean; scope_reason: string | null; exempt: boolean; exempt_reason: string | null; is_compliant: boolean; critical_violations: number; total_violations: number; violations: RuleEngineViolation[]; passed_checks: string[] }
export interface RuleResult { rule_id: string; rule_number: string; rule_title: string; requirement: string; extracted_value: string | null; status: RuleResultStatus; severity: string; confidence: Confidence; evidence_image_id: string | null; evidence_face: string | null; explanation: string; consumer_explanation: string; official_source: string }
export interface ExtractedProduct { product_name: string; brand: string | null; category: string; manufacturer: string | null; net_quantity: string | null; mrp: string | null; mfg_date: string | null; batch_lot: string | null; consumer_care: string | null }
export interface ScanRecord { id: string; owner_id: string; owner_role: string; product_name: string; brand: string | null; manufacturer: string; category: string; region: string; inspector: string; status: ComplianceStatus; scanned_at: string; image_url: string; image_ids: string[]; images: ScanImage[]; declarations: DeclarationResult[]; extracted_product: ExtractedProduct | null; ocr_texts: Array<Record<string, unknown>>; processing_notes: string[]; rule_results: RuleResult[]; violation_count: number; review_status: ReviewStatus; remarks: string; consumer_review: string; rule_engine_report: RuleEngineReport | null }
export interface UploadConfig { max_images: number; max_file_size_bytes: number; max_total_size_bytes: number; supported_mime_types: string[]; min_width: number; min_height: number; recommended_width: number; recommended_height: number }
export interface BreakdownPoint { name: string; value: number }
export interface TrendPoint { month: string; compliant: number; violations: number }
export interface DashboardResponse { stats: { total_scanned: number; violation_rate: number; pending_reviews: number; reports_issued: number }; violation_types: BreakdownPoint[]; regions: BreakdownPoint[]; trend: TrendPoint[] }
export interface RuleItem { id: string; rule_number: string; title: string; rule_code: string; requirement: string; description: string; applicability: string; required_declaration: string | null; detection_keywords: string[]; validation_logic: string; violation_condition: string; severity: string; consumer_explanation: string; inspector_explanation: string; official_source: string; min_font_height_mm: number; mandatory: boolean; updated_at: string }