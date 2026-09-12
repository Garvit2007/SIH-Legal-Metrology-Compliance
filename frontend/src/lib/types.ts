export type ComplianceStatus = "compliant" | "non_compliant" | "review";
export type ReviewStatus = "not_required" | "pending" | "verified";

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface DeclarationResult {
  key: string;
  field_name: string;
  detected_value: string | null;
  status: ComplianceStatus;
  rule_code: string;
  requirement: string;
  reason: string;
  font_size_mm: number | null;
  bbox: BoundingBox;
}

export interface ScanRecord {
  id: string;
  product_name: string;
  manufacturer: string;
  category: string;
  region: string;
  inspector: string;
  status: ComplianceStatus;
  scanned_at: string;
  image_url: string;
  declarations: DeclarationResult[];
  violation_count: number;
  review_status: ReviewStatus;
  remarks: string;
}

export interface BreakdownPoint {
  name: string;
  value: number;
}

export interface TrendPoint {
  month: string;
  compliant: number;
  violations: number;
}

export interface DashboardResponse {
  stats: {
    total_scanned: number;
    violation_rate: number;
    pending_reviews: number;
    reports_issued: number;
  };
  violation_types: BreakdownPoint[];
  regions: BreakdownPoint[];
  trend: TrendPoint[];
}

export interface RuleItem {
  id: string;
  title: string;
  rule_code: string;
  requirement: string;
  min_font_height_mm: number;
  mandatory: boolean;
  updated_at: string;
}