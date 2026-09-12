import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  ArrowLeft,
  ArrowUpRight,
  BarChart3,
  Bell,
  BookOpen,
  Camera,
  Check,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  Download,
  FileCheck2,
  FileText,
  Filter,
  Flag,
  LayoutDashboard,
  ListFilter,
  MapPin,
  Menu,
  Search,
  ScanLine,
  Scale,
  ShieldCheck,
  Upload,
  Users,
  X,
} from "lucide-react";
import { motion } from "motion/react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiGet, apiPatch, apiPost } from "@/lib/api";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "@/lib/recharts";
import type { ComplianceStatus, DashboardResponse, DeclarationResult, RuleItem, ScanRecord } from "@/lib/types";

type Role = "inspector" | "reviewer" | "admin";
type View = "dashboard" | "scan" | "repository" | "analytics" | "rules" | "users";
type ScanStep = "idle" | "processing" | "results" | "report";

const DEMO_IMAGE = "https://images.unsplash.com/photo-1618381297523-e6c0ab13a5b2?auto=format&fit=crop&w=1400&q=85";

const roleMeta: Record<Role, { label: string; short: string; name: string; color: string }> = {
  inspector: { label: "Field Inspector", short: "INS", name: "Aditi Rao", color: "bg-blue-600" },
  reviewer: { label: "Compliance Reviewer", short: "REV", name: "Vivek Sharma", color: "bg-amber-600" },
  admin: { label: "Admin Officer", short: "ADM", name: "Meera Nair", color: "bg-slate-700" },
};

const roleNav: Record<Role, { id: View; label: string; icon: typeof LayoutDashboard }[]> = {
  inspector: [
    { id: "dashboard", label: "Overview", icon: LayoutDashboard },
    { id: "scan", label: "Scan label", icon: ScanLine },
    { id: "repository", label: "Inspection log", icon: ClipboardCheck },
    { id: "rules", label: "Rules reference", icon: BookOpen },
  ],
  reviewer: [
    { id: "dashboard", label: "Overview", icon: LayoutDashboard },
    { id: "repository", label: "Review queue", icon: ClipboardCheck },
    { id: "analytics", label: "Analytics", icon: BarChart3 },
    { id: "rules", label: "Rules reference", icon: BookOpen },
  ],
  admin: [
    { id: "dashboard", label: "Overview", icon: LayoutDashboard },
    { id: "repository", label: "Repository", icon: ClipboardCheck },
    { id: "analytics", label: "Analytics", icon: BarChart3 },
    { id: "users", label: "Users & roles", icon: Users },
    { id: "rules", label: "Rules database", icon: BookOpen },
  ],
};

const fallbackDeclarations: DeclarationResult[] = [
  { key: "manufacturer_details", field_name: "Manufacturer / Packer", detected_value: "Shakti Foods Pvt. Ltd., Okhla Industrial Area, New Delhi 110020", status: "compliant", rule_code: "Rule 6(1)(a)", requirement: "Complete name, address and PIN code", reason: "Complete address detected with PIN code.", font_size_mm: 1.8, bbox: { x: 10, y: 67, width: 73, height: 11 } },
  { key: "net_quantity", field_name: "Net Quantity", detected_value: "Net Qty. 500 g", status: "compliant", rule_code: "Rule 6(1)(c)", requirement: "Standard unit on the Principal Display Panel", reason: "Standard metric unit detected on the front panel.", font_size_mm: 2.8, bbox: { x: 10, y: 18, width: 25, height: 10 } },
  { key: "mrp", field_name: "Maximum Retail Price", detected_value: "MRP ₹120.00 (incl. of all taxes)", status: "compliant", rule_code: "Rule 6(1)(e)", requirement: "MRP inclusive of all taxes", reason: "Inclusive tax declaration is present and readable.", font_size_mm: 2.6, bbox: { x: 54, y: 79, width: 35, height: 9 } },
  { key: "date_mfg", field_name: "Month / Year of Manufacture", detected_value: "Packed on: 05/2024", status: "compliant", rule_code: "Rule 6(1)(d)", requirement: "Month and year in MM/YYYY format", reason: "Valid month/year format detected.", font_size_mm: 1.6, bbox: { x: 10, y: 83, width: 35, height: 8 } },
  { key: "consumer_care", field_name: "Consumer Care", detected_value: "care@shaktifoods.in · 1800 123 4567", status: "review", rule_code: "Rule 6(2)", requirement: "Name, address, telephone and email", reason: "Email and telephone detected; address line needs visual verification.", font_size_mm: 1.1, bbox: { x: 10, y: 56, width: 78, height: 9 } },
  { key: "font_size_pdp", field_name: "Font Height / Legibility", detected_value: "1.2 mm estimated", status: "non_compliant", rule_code: "Rule 7 & Table-I", requirement: "Minimum 1.5 mm for this PDP area", reason: "Estimated height is 1.2mm, below the required 1.5mm minimum.", font_size_mm: 1.2, bbox: { x: 10, y: 38, width: 73, height: 12 } },
];

const fallbackScan: ScanRecord = {
  id: "demo-local-scan",
  product_name: "Shakti Premium Atta 5kg",
  manufacturer: "Shakti Foods Pvt. Ltd.",
  category: "Staples",
  region: "Delhi NCR",
  inspector: "INS-042 · Aditi Rao",
  status: "non_compliant",
  scanned_at: "2024-06-20T10:30:00Z",
  image_url: DEMO_IMAGE,
  declarations: fallbackDeclarations,
  violation_count: 1,
  review_status: "pending",
  remarks: "Verify the principal display panel font height before notice issue.",
  rule_engine_report: null,
};

const fallbackDashboard: DashboardResponse = {
  stats: { total_scanned: 128, violation_rate: 18.8, pending_reviews: 14, reports_issued: 86 },
  violation_types: [{ name: "Font Height / Legibility", value: 24 }, { name: "MRP Statement", value: 18 }, { name: "Manufacturer Details", value: 13 }, { name: "Net Quantity", value: 9 }],
  regions: [{ name: "Delhi NCR", value: 42 }, { name: "Maharashtra", value: 31 }, { name: "Karnataka", value: 24 }, { name: "Gujarat", value: 18 }],
  trend: [{ month: "Jan", compliant: 28, violations: 6 }, { month: "Feb", compliant: 34, violations: 7 }, { month: "Mar", compliant: 42, violations: 5 }, { month: "Apr", compliant: 39, violations: 9 }, { month: "May", compliant: 48, violations: 8 }, { month: "Jun", compliant: 44, violations: 6 }],
};

const formatDate = (value: string) => new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", year: "numeric" }).format(new Date(value));

function statusMeta(status: ComplianceStatus) {
  if (status === "compliant") return { label: "Compliant", icon: CheckCircle2, className: "border-emerald-200 bg-emerald-50 text-emerald-700" };
  if (status === "non_compliant") return { label: "Violation", icon: AlertCircle, className: "border-red-200 bg-red-50 text-red-700" };
  return { label: "Needs review", icon: Flag, className: "border-amber-200 bg-amber-50 text-amber-700" };
}

function StatusPill({ status }: { status: ComplianceStatus }) {
  const meta = statusMeta(status);
  const Icon = meta.icon;
  return <span data-testid={`status-pill-${status}`} className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${meta.className}`}><Icon className="size-3.5" />{meta.label}</span>;
}

export default function Home() {
  const queryClient = useQueryClient();
  const [role, setRole] = useState<Role>("inspector");
  const [view, setView] = useState<View>("dashboard");
  const [scanStep, setScanStep] = useState<ScanStep>("idle");
  const [activeScan, setActiveScan] = useState<ScanRecord | null>(null);
  const [remarks, setRemarks] = useState("");
  const [search, setSearch] = useState("");
  const [ruleSearch, setRuleSearch] = useState("");
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const scansQuery = useQuery({ queryKey: ["compliance-scans"], queryFn: () => apiGet<ScanRecord[]>("/compliance/scans"), retry: false });
  const dashboardQuery = useQuery({ queryKey: ["compliance-dashboard"], queryFn: () => apiGet<DashboardResponse>("/compliance/dashboard"), retry: false });
  const rulesQuery = useQuery({ queryKey: ["compliance-rules"], queryFn: () => apiGet<RuleItem[]>("/compliance/rules"), retry: false });
  const scans = scansQuery.data?.length ? scansQuery.data : [fallbackScan];
  const dashboard = dashboardQuery.data ?? fallbackDashboard;
  const rules = rulesQuery.data ?? [];

  const scanMutation = useMutation({
    mutationFn: (payload: { image_base64?: string; mime_type?: string; image_url?: string }) => apiPost<ScanRecord>("/compliance/scans", { ...payload, product_name: "Uploaded packaged commodity", category: "Food & Grocery", region: "Delhi NCR", inspector: "INS-042 · Aditi Rao" }),
    onSuccess: (scan) => {
      setActiveScan(scan);
      setRemarks(scan.remarks);
      setScanStep("results");
      void queryClient.invalidateQueries({ queryKey: ["compliance-scans"] });
      void queryClient.invalidateQueries({ queryKey: ["compliance-dashboard"] });
      toast.success("Label analysis complete", { description: "Review the highlighted declarations before filing the report." });
    },
    onError: () => {
      setActiveScan(fallbackScan);
      setRemarks(fallbackScan.remarks);
      setScanStep("results");
      toast.warning("Live vision unavailable", { description: "Showing the deterministic demo result so the inspection can continue." });
    },
  });

  const reviewMutation = useMutation({
    mutationFn: (payload: { id: string; remarks: string }) => apiPatch<ScanRecord>(`/compliance/scans/${payload.id}`, { remarks: payload.remarks, review_status: "verified" }),
    onSuccess: (scan) => {
      setActiveScan(scan);
      toast.success("Review saved", { description: "The inspection record is now marked as verified." });
      void queryClient.invalidateQueries({ queryKey: ["compliance-scans"] });
      void queryClient.invalidateQueries({ queryKey: ["compliance-dashboard"] });
    },
  });

  const filteredScans = useMemo(() => scans.filter((scan) => `${scan.product_name} ${scan.manufacturer} ${scan.category} ${scan.region}`.toLowerCase().includes(search.toLowerCase())), [scans, search]);
  const filteredRules = useMemo(() => rules.filter((rule) => `${rule.title} ${rule.rule_code} ${rule.requirement}`.toLowerCase().includes(ruleSearch.toLowerCase())), [rules, ruleSearch]);

  const selectRole = (nextRole: Role) => {
    setRole(nextRole);
    setView("dashboard");
    setMobileNavOpen(false);
    toast.success(`${roleMeta[nextRole].label} workspace active`, { description: `Prototype session · ${roleMeta[nextRole].name}` });
  };

  const openScan = (scan: ScanRecord) => {
    setActiveScan(scan);
    setRemarks(scan.remarks);
    setScanStep("results");
    setView("scan");
  };

  const handleFile = (file: File | undefined) => {
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      toast.error("Please upload a PNG, JPEG, or WEBP label image.");
      return;
    }
    setScanStep("processing");
    const reader = new FileReader();
    reader.onload = () => window.setTimeout(() => scanMutation.mutate({ image_base64: String(reader.result), mime_type: file.type }), 850);
    reader.readAsDataURL(file);
  };

  const startDemoScan = () => {
    setScanStep("processing");
    window.setTimeout(() => scanMutation.mutate({ image_url: DEMO_IMAGE }), 850);
  };

  const downloadReport = (format: "pdf" | "docx") => {
    if (!activeScan) return;
    const text = `LEGAL METROLOGY INSPECTION REPORT\n\nProduct: ${activeScan.product_name}\nManufacturer: ${activeScan.manufacturer}\nRegion: ${activeScan.region}\nInspector: ${activeScan.inspector}\nStatus: ${statusMeta(activeScan.status).label}\n\nDECLARATIONS\n${activeScan.declarations.map((item) => `${item.field_name}: ${item.detected_value ?? "Not detected"} — ${statusMeta(item.status).label}. ${item.reason}`).join("\n")}\n\nInspector remarks: ${remarks || "None recorded"}`;
    const blob = new Blob([text], { type: format === "pdf" ? "application/pdf" : "application/vnd.openxmlformats-officedocument.wordprocessingml.document" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `legal-metrology-${activeScan.id}.${format}`;
    anchor.click();
    URL.revokeObjectURL(url);
    toast.success(`${format.toUpperCase()} report downloaded`);
  };

  const nav = roleNav[role];
  const activeRole = roleMeta[role];

  return (
    <div data-testid="legal-metrology-app" className="min-h-svh bg-slate-50 text-slate-900">
      <header data-testid="government-portal-header" className="sticky top-0 z-40 border-b border-slate-200 bg-white/95 shadow-sm backdrop-blur-md">
        <div className="flex h-12 items-center justify-between bg-[#0f172a] px-4 text-white sm:px-6 lg:px-8">
          <div data-testid="government-banner" className="flex items-center gap-2 text-[11px] font-semibold tracking-wide text-slate-200"><ShieldCheck className="size-4 text-blue-300" /> GOVERNMENT OF INDIA <span className="hidden text-slate-500 sm:inline">/</span><span className="hidden font-normal text-slate-400 sm:inline">Department of Consumer Affairs</span></div>
          <div data-testid="secure-session-indicator" className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider text-emerald-300"><span className="size-1.5 rounded-full bg-emerald-400" /> Prototype session active</div>
        </div>
        <div className="flex h-[72px] items-center justify-between px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <div data-testid="portal-emblem" className="flex size-10 items-center justify-center rounded-xl bg-blue-900 text-white shadow-lg shadow-blue-900/20"><Scale className="size-5" /></div>
            <div><p data-testid="portal-department" className="text-[10px] font-bold uppercase tracking-[0.18em] text-blue-900">Legal Metrology Enforcement Portal</p><h1 data-testid="portal-title" className="font-heading text-lg font-bold tracking-tight text-slate-900 sm:text-xl">Packaged Commodities · 2011 Rules</h1></div>
          </div>
          <div className="flex items-center gap-2 sm:gap-4">
            <button type="button" data-testid="notification-button" className="relative flex size-10 items-center justify-center rounded-lg text-slate-500 transition-colors hover:bg-slate-100 hover:text-blue-900"><Bell className="size-5" /><span className="absolute right-2 top-2 size-1.5 rounded-full bg-red-500" /></button>
            <div data-testid="active-role-profile" className="hidden items-center gap-3 border-l border-slate-200 pl-4 sm:flex"><div className={`flex size-9 items-center justify-center rounded-lg text-xs font-bold text-white ${activeRole.color}`}>{activeRole.short}</div><div><p data-testid="active-role-name" className="text-sm font-bold text-slate-900">{activeRole.name}</p><p data-testid="active-role-label" className="text-[11px] text-slate-500">{activeRole.label}</p></div></div>
            <Button type="button" data-testid="mobile-navigation-toggle" variant="outline" size="icon" className="sm:hidden" onClick={() => setMobileNavOpen((open) => !open)}><Menu className="size-4" /></Button>
          </div>
        </div>
      </header>

      <div className="mx-auto flex max-w-[1600px]">
        <aside data-testid="primary-navigation" className={`${mobileNavOpen ? "block" : "hidden"} absolute inset-x-0 top-[132px] z-30 border-b border-slate-200 bg-white p-3 shadow-xl sm:relative sm:top-0 sm:block sm:w-60 sm:shrink-0 sm:border-0 sm:border-r sm:bg-transparent sm:p-4 sm:shadow-none lg:w-64 lg:p-6`}>
          <div data-testid="role-switcher" className="mb-6 rounded-2xl border border-blue-100 bg-blue-50/70 p-3"><p data-testid="role-switcher-label" className="mb-2 px-1 text-[10px] font-bold uppercase tracking-[0.16em] text-blue-900">Demo workspace</p><div className="grid grid-cols-3 gap-1 rounded-xl bg-white p-1 shadow-sm">{(Object.keys(roleMeta) as Role[]).map((item) => <button key={item} type="button" data-testid={`role-switcher-${item}`} onClick={() => selectRole(item)} className={`min-h-11 rounded-lg px-1 text-[10px] font-bold transition-colors ${role === item ? "bg-blue-900 text-white shadow-md" : "text-slate-500 hover:bg-slate-100 hover:text-slate-900"}`}>{roleMeta[item].short}<span className="mt-0.5 block font-medium opacity-80">{item === "inspector" ? "Field" : item === "reviewer" ? "Review" : "Admin"}</span></button>)}</div></div>
          <nav aria-label="Main navigation" className="space-y-1">{nav.map((item) => { const Icon = item.icon; return <button key={item.id} type="button" data-testid={`navigation-${item.id}`} onClick={() => { setView(item.id); setMobileNavOpen(false); }} className={`flex min-h-11 w-full items-center gap-3 rounded-xl px-3 text-left text-sm font-semibold transition-all ${view === item.id ? "bg-blue-900 text-white shadow-lg shadow-blue-900/15" : "text-slate-600 hover:bg-white hover:text-blue-900 hover:shadow-sm"}`}><Icon className="size-[18px]" />{item.label}{item.id === "repository" && role === "reviewer" ? <span data-testid="pending-review-count" className="ml-auto rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-800">14</span> : null}</button>; })}</nav>
          <div data-testid="nav-help-card" className="mt-10 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"><p data-testid="nav-help-label" className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-400">Need a rule?</p><p data-testid="nav-help-copy" className="mt-2 text-xs leading-relaxed text-slate-600">Search the reference library for declaration requirements and font thresholds.</p><button type="button" data-testid="nav-help-link" onClick={() => setView("rules")} className="mt-3 inline-flex items-center gap-1 text-xs font-bold text-blue-900 hover:text-blue-600">Open rules <ArrowUpRight className="size-3" /></button></div>
        </aside>

        <main data-testid="main-content" className="min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          {view === "dashboard" && <DashboardView role={role} dashboard={dashboard} scans={scans} onScan={() => { setView("scan"); setScanStep("idle"); }} onOpenScan={openScan} onView={setView} />}
          {view === "scan" && <ScanView step={scanStep} activeScan={activeScan} remarks={remarks} setRemarks={setRemarks} isProcessing={scanMutation.isPending} onFile={handleFile} onDemo={startDemoScan} onBack={() => { setView("dashboard"); setScanStep("idle"); }} onResults={() => setScanStep("results")} onReport={() => setScanStep("report")} onDownload={downloadReport} onSave={() => activeScan && reviewMutation.mutate({ id: activeScan.id, remarks })} isSaving={reviewMutation.isPending} />}
          {view === "repository" && <RepositoryView scans={filteredScans} search={search} setSearch={setSearch} onOpenScan={openScan} role={role} />}
          {view === "analytics" && <AnalyticsView dashboard={dashboard} />}
          {view === "rules" && <RulesView rules={filteredRules} search={ruleSearch} setSearch={setRuleSearch} role={role} />}
          {view === "users" && <UsersView />}
        </main>
      </div>
    </div>
  );
}

function PageHeading({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return <div className="mb-7 flex flex-col justify-between gap-4 border-b border-slate-200 pb-6 sm:flex-row sm:items-end"><div><p data-testid="page-eyebrow" className="mb-2 text-[10px] font-bold uppercase tracking-[0.18em] text-blue-700">{eyebrow}</p><h2 data-testid="page-title" className="font-heading text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">{title}</h2><p data-testid="page-description" className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-500">{description}</p></div>{action}</div>;
}

function DashboardView({ role, dashboard, scans, onScan, onOpenScan, onView }: { role: Role; dashboard: DashboardResponse; scans: ScanRecord[]; onScan: () => void; onOpenScan: (scan: ScanRecord) => void; onView: (view: View) => void }) {
  const meta = roleMeta[role];
  return <>
    <PageHeading eyebrow={`${meta.label} workspace · 20 Jun 2024`} title={role === "inspector" ? "Ready for the next inspection?" : role === "reviewer" ? "Compliance at a glance" : "National enforcement overview"} description={role === "inspector" ? "Capture declarations from the package, verify the evidence, and keep the inspection record audit-ready." : "Monitor label compliance, prioritize flagged inspections, and keep the department’s enforcement picture current."} action={role === "inspector" ? <Button type="button" data-testid="dashboard-scan-cta" size="lg" className="min-h-11 gap-2 bg-blue-900 px-5 hover:bg-blue-800" onClick={onScan}><ScanLine className="size-4" /> Scan new product</Button> : <Button type="button" data-testid="dashboard-repository-cta" variant="outline" size="lg" className="min-h-11 gap-2" onClick={() => onView("repository")}><ClipboardCheck className="size-4" /> Open {role === "admin" ? "repository" : "review queue"}</Button>} />
    <div data-testid="dashboard-role-callout" className="mb-6 grid overflow-hidden rounded-2xl bg-[#0f172a] text-white shadow-xl shadow-slate-900/10 lg:grid-cols-[1fr_330px]"><div className="relative p-6 sm:p-8"><div className="absolute right-[-30px] top-[-70px] size-64 rounded-full border-[26px] border-blue-400/10" /><div className="relative"><div className="mb-5 flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-blue-300"><ShieldCheck className="size-4" /> Rules-based vision review</div><h3 data-testid="callout-title" className="max-w-xl font-heading text-2xl font-bold tracking-tight sm:text-3xl">See the evidence before you issue the notice.</h3><p data-testid="callout-description" className="mt-3 max-w-lg text-sm leading-relaxed text-slate-300">Gemini Vision extracts declarations, then maps every finding to its Legal Metrology rule and evidence region.</p><button type="button" data-testid="callout-rules-link" onClick={() => onView("rules")} className="mt-5 inline-flex items-center gap-2 text-sm font-bold text-white hover:text-blue-200">Review the rule library <ChevronRight className="size-4" /></button></div></div><div data-testid="callout-assurance" className="border-t border-white/10 bg-white/[0.04] p-6 lg:border-l lg:border-t-0"><p data-testid="assurance-label" className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">Field assurance</p><p data-testid="assurance-value" className="mt-3 font-mono text-3xl font-bold text-emerald-300">98.4%</p><p data-testid="assurance-copy" className="mt-2 text-xs leading-relaxed text-slate-400">of seeded scans have usable declaration evidence attached for reviewer verification.</p><div className="mt-6 h-1.5 overflow-hidden rounded-full bg-white/10"><div className="h-full w-[84%] rounded-full bg-emerald-400" /></div><p data-testid="assurance-footnote" className="mt-2 text-[11px] text-slate-500">Evidence quality · last 30 days</p></div></div>
    <div data-testid="dashboard-metrics" className="mb-7 grid grid-cols-2 gap-3 sm:grid-cols-4 sm:gap-4"><MetricCard label="Total scanned" value={String(dashboard.stats.total_scanned)} change="+12.6%" icon={ScanLine} tone="blue" /><MetricCard label="Violation rate" value={`${dashboard.stats.violation_rate}%`} change="-3.2%" icon={AlertCircle} tone="red" /><MetricCard label="Pending reviews" value={String(dashboard.stats.pending_reviews)} change="Needs action" icon={Flag} tone="amber" /><MetricCard label="Reports issued" value={String(dashboard.stats.reports_issued)} change="This quarter" icon={FileCheck2} tone="green" /></div>
    <div className="grid gap-6 xl:grid-cols-[1.5fr_1fr]"><Card data-testid="recent-inspections-card" className="border-slate-200 shadow-sm"><CardHeader className="flex flex-row items-center justify-between border-b border-slate-100 pb-4"><div><CardTitle data-testid="recent-inspections-title" className="font-heading text-lg font-bold">Recent inspections</CardTitle><p data-testid="recent-inspections-description" className="mt-1 text-xs text-slate-500">Latest field activity across assigned regions</p></div><button type="button" data-testid="recent-inspections-view-all" onClick={() => onView("repository")} className="text-xs font-bold text-blue-900 hover:text-blue-600">View all</button></CardHeader><CardContent className="p-0">{scans.slice(0, 5).map((scan) => <button key={scan.id} type="button" data-testid={`recent-scan-${scan.id}`} onClick={() => onOpenScan(scan)} className="flex min-h-[72px] w-full items-center gap-3 border-b border-slate-100 px-4 text-left transition-colors last:border-b-0 hover:bg-slate-50 sm:px-6"><div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-500"><FileText className="size-4" /></div><div className="min-w-0 flex-1"><p data-testid={`recent-scan-name-${scan.id}`} className="truncate text-sm font-bold text-slate-800">{scan.product_name}</p><p data-testid={`recent-scan-meta-${scan.id}`} className="mt-1 truncate text-xs text-slate-500">{scan.manufacturer} · {scan.region} · {formatDate(scan.scanned_at)}</p></div><StatusPill status={scan.status} /><ChevronRight className="hidden size-4 text-slate-300 sm:block" /></button>)}</CardContent></Card><Card data-testid="priority-review-card" className="border-slate-200 shadow-sm"><CardHeader className="border-b border-slate-100 pb-4"><CardTitle data-testid="priority-review-title" className="font-heading text-lg font-bold">Priority review</CardTitle><p data-testid="priority-review-description" className="mt-1 text-xs text-slate-500">Records that may need an officer decision</p></CardHeader><CardContent className="space-y-3 p-4 sm:p-6">{scans.filter((scan) => scan.status !== "compliant").slice(0, 3).map((scan) => <button key={scan.id} type="button" data-testid={`priority-scan-${scan.id}`} onClick={() => onOpenScan(scan)} className="w-full rounded-xl border border-amber-100 bg-amber-50/60 p-3 text-left transition-all hover:-translate-y-0.5 hover:border-amber-200 hover:shadow-sm"><div className="flex items-start justify-between gap-3"><div><p data-testid={`priority-scan-name-${scan.id}`} className="text-sm font-bold text-slate-800">{scan.product_name}</p><p data-testid={`priority-scan-review-${scan.id}`} className="mt-1 text-xs text-slate-500">{scan.violation_count || 1} finding{scan.violation_count === 1 ? "" : "s"} · {scan.review_status === "verified" ? "Verified" : "Pending review"}</p></div><ArrowUpRight className="size-4 text-amber-700" /></div></button>)}<button type="button" data-testid="priority-review-open-queue" onClick={() => onView("repository")} className="flex min-h-11 w-full items-center justify-center gap-2 rounded-xl border border-dashed border-slate-300 text-xs font-bold text-slate-600 hover:border-blue-300 hover:text-blue-900"><ListFilter className="size-4" /> Open review queue</button></CardContent></Card></div>
  </>;
}

function MetricCard({ label, value, change, icon: Icon, tone }: { label: string; value: string; change: string; icon: typeof ScanLine; tone: "blue" | "red" | "amber" | "green" }) {
  const colors = { blue: "bg-blue-50 text-blue-700", red: "bg-red-50 text-red-700", amber: "bg-amber-50 text-amber-700", green: "bg-emerald-50 text-emerald-700" };
  return <Card data-testid={`metric-card-${label.toLowerCase().replaceAll(" ", "-")}`} className="border-slate-200 shadow-sm"><CardContent className="p-4 sm:p-5"><div className="flex items-start justify-between gap-2"><div><p data-testid={`metric-label-${label.toLowerCase().replaceAll(" ", "-")}`} className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{label}</p><p data-testid={`metric-value-${label.toLowerCase().replaceAll(" ", "-")}`} className="mt-2 font-mono text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">{value}</p></div><div className={`flex size-9 items-center justify-center rounded-xl ${colors[tone]}`}><Icon className="size-4" /></div></div><p data-testid={`metric-change-${label.toLowerCase().replaceAll(" ", "-")}`} className="mt-3 text-[11px] font-semibold text-slate-500">{change}</p></CardContent></Card>;
}

function ScanView({ step, activeScan, remarks, setRemarks, isProcessing, onFile, onDemo, onBack, onResults, onReport, onDownload, onSave, isSaving }: { step: ScanStep; activeScan: ScanRecord | null; remarks: string; setRemarks: (value: string) => void; isProcessing: boolean; onFile: (file: File | undefined) => void; onDemo: () => void; onBack: () => void; onResults: () => void; onReport: () => void; onDownload: (format: "pdf" | "docx") => void; onSave: () => void; isSaving: boolean }) {
  if (step === "report" && activeScan) return <ReportView scan={activeScan} remarks={remarks} setRemarks={setRemarks} onBack={onResults} onDownload={onDownload} onSave={onSave} isSaving={isSaving} />;
  return <>
    <PageHeading eyebrow="Field inspection workflow" title={step === "results" && activeScan ? "Declaration review" : "Scan a product label"} description={step === "results" && activeScan ? "Evidence is mapped to each required declaration. Confirm the findings before generating the official report." : "Use a clear front, back, or close-up label image. The vision check is designed for field conditions and reviewer handoff."} action={step === "results" && activeScan ? <Button type="button" data-testid="scan-report-button" size="lg" className="min-h-11 gap-2 bg-blue-900 hover:bg-blue-800" onClick={onReport}><FileCheck2 className="size-4" /> Prepare report</Button> : null} />
    {step === "idle" && <UploadPanel onFile={onFile} onDemo={onDemo} />}
    {step === "processing" && <ProcessingPanel isProcessing={isProcessing} />}
    {step === "results" && activeScan && <ResultsPanel scan={activeScan} onBack={onBack} onReport={onReport} />}
  </>;
}

function UploadPanel({ onFile, onDemo }: { onFile: (file: File | undefined) => void; onDemo: () => void }) {
  return <div data-testid="scan-upload-panel" className="grid gap-6 lg:grid-cols-[1.4fr_0.8fr]"><Card className="border-slate-200 shadow-sm"><CardContent className="p-5 sm:p-8"><label data-testid="scan-dropzone" htmlFor="label-image-input" className="group flex min-h-[310px] cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-blue-200 bg-blue-50/40 p-6 text-center transition-all hover:border-blue-500 hover:bg-blue-50"><div className="mb-5 flex size-16 items-center justify-center rounded-2xl bg-white text-blue-700 shadow-lg shadow-blue-900/10 transition-transform group-hover:-translate-y-1"><Upload className="size-7" /></div><p data-testid="upload-title" className="font-heading text-xl font-bold text-slate-900">Drop a label image here</p><p data-testid="upload-description" className="mt-2 max-w-sm text-sm leading-relaxed text-slate-500">Upload a clear PNG, JPEG, or WEBP image of the principal display panel.</p><span data-testid="upload-browse-label" className="mt-5 inline-flex min-h-11 items-center rounded-lg bg-blue-900 px-4 text-sm font-bold text-white shadow-sm">Browse image</span><p data-testid="upload-format-note" className="mt-4 text-[11px] font-medium text-slate-400">Maximum 10MB · Keep text sharp and well lit</p></label><input id="label-image-input" data-testid="scan-image-input" className="sr-only" type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => onFile(event.target.files?.[0])} /></CardContent></Card><div className="space-y-4"><Card data-testid="capture-options-card" className="border-slate-200 shadow-sm"><CardHeader><CardTitle data-testid="capture-options-title" className="font-heading text-lg font-bold">Capture options</CardTitle></CardHeader><CardContent className="space-y-3"><button type="button" data-testid="camera-capture-button" className="flex min-h-12 w-full items-center gap-3 rounded-xl border border-slate-200 px-4 text-left text-sm font-bold text-slate-700 transition-colors hover:border-blue-300 hover:bg-blue-50 hover:text-blue-900" onClick={() => toast.info("Camera capture is ready in the mobile build", { description: "For this prototype, upload a camera photo from the device gallery." })}><Camera className="size-5 text-blue-700" /> Use camera capture <ChevronRight className="ml-auto size-4 text-slate-300" /></button><button type="button" data-testid="demo-scan-button" className="flex min-h-12 w-full items-center gap-3 rounded-xl border border-blue-200 bg-blue-50 px-4 text-left text-sm font-bold text-blue-900 transition-colors hover:bg-blue-100" onClick={onDemo}><ScanLine className="size-5" /> Run seeded demo scan <ChevronRight className="ml-auto size-4 text-blue-400" /></button></CardContent></Card><div data-testid="scan-guidance-card" className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><div className="mb-3 flex items-center gap-2"><ShieldCheck className="size-4 text-emerald-600" /><p data-testid="scan-guidance-title" className="text-sm font-bold text-slate-900">For a better result</p></div><ul className="space-y-3 text-xs leading-relaxed text-slate-500"><li data-testid="scan-guidance-light" className="flex gap-2"><Check className="mt-0.5 size-3.5 shrink-0 text-emerald-600" /> Photograph in even light without glare</li><li data-testid="scan-guidance-angle" className="flex gap-2"><Check className="mt-0.5 size-3.5 shrink-0 text-emerald-600" /> Keep the label parallel and fill the frame</li><li data-testid="scan-guidance-evidence" className="flex gap-2"><Check className="mt-0.5 size-3.5 shrink-0 text-emerald-600" /> Include the complete principal display panel</li></ul></div></div></div>;
}

function ProcessingPanel({ isProcessing }: { isProcessing: boolean }) {
  return <motion.div data-testid="scan-processing-panel" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="grid min-h-[440px] place-items-center rounded-2xl border border-blue-100 bg-white p-8 text-center shadow-sm"><div><div className="relative mx-auto mb-7 flex size-20 items-center justify-center rounded-2xl bg-blue-50 text-blue-700"><ScanLine className="size-9 animate-pulse" /><span className="absolute inset-[-10px] animate-ping rounded-3xl border border-blue-300/50" /></div><p data-testid="processing-kicker" className="text-[10px] font-bold uppercase tracking-[0.18em] text-blue-700">Vision analysis in progress</p><h3 data-testid="processing-title" className="mt-3 font-heading text-2xl font-bold text-slate-900">Extracting declarations...</h3><p data-testid="processing-description" className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-slate-500">Checking the Principal Display Panel against MRP, quantity, manufacturer, date, consumer care, and font-height requirements.</p><div data-testid="processing-progress" className="mx-auto mt-8 max-w-sm"><div className="h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full w-3/4 animate-pulse rounded-full bg-blue-600" /></div><div className="mt-3 flex justify-between text-[11px] font-semibold text-slate-400"><span>Reading label regions</span><span>{isProcessing ? "Live" : "Demo"}</span></div></div></div></motion.div>;
}

function ResultsPanel({ scan, onBack, onReport }: { scan: ScanRecord; onBack: () => void; onReport: () => void }) {
  const counts = { compliant: scan.declarations.filter((item) => item.status === "compliant").length, review: scan.declarations.filter((item) => item.status === "review").length, non_compliant: scan.declarations.filter((item) => item.status === "non_compliant").length };
  return <div data-testid="scan-results-panel"><div className="mb-5 flex flex-wrap items-center gap-3"><button type="button" data-testid="scan-results-back-button" onClick={onBack} className="inline-flex min-h-11 items-center gap-2 text-sm font-bold text-slate-500 hover:text-blue-900"><ArrowLeft className="size-4" /> New scan</button><span className="text-slate-300">/</span><span data-testid="scan-result-product" className="text-sm font-bold text-slate-800">{scan.product_name}</span><StatusPill status={scan.status} /></div><div className="mb-6 grid grid-cols-3 gap-3 sm:max-w-md"><ResultCount label="Pass" value={counts.compliant} tone="green" /><ResultCount label="Review" value={counts.review} tone="amber" /><ResultCount label="Violation" value={counts.non_compliant} tone="red" /></div><div className="grid grid-cols-1 gap-6 lg:grid-cols-12"><Card data-testid="annotated-image-card" className="overflow-hidden border-slate-200 shadow-sm lg:col-span-7"><CardHeader className="flex flex-row items-center justify-between border-b border-slate-100 pb-4"><div><CardTitle data-testid="annotated-image-title" className="font-heading text-lg font-bold">Evidence map</CardTitle><p data-testid="annotated-image-description" className="mt-1 text-xs text-slate-500">Select a box to trace the finding to its declaration.</p></div><Badge data-testid="vision-engine-badge" variant="outline" className="gap-1.5 border-blue-200 text-blue-800"><ScanLine className="size-3" /> Gemini OCR · {scan.rule_engine_report ? `Rule Engine ${scan.rule_engine_report.rule_version}` : "Legacy result"}</Badge></CardHeader><CardContent className="p-4 sm:p-6"><div data-testid="annotated-product-image" className="relative aspect-[4/3] overflow-hidden rounded-xl bg-slate-900"><img src={scan.image_url} alt="Packaged commodity label evidence" className="size-full object-cover opacity-90" /><div className="absolute inset-0 bg-gradient-to-t from-slate-950/50 to-transparent" />{scan.declarations.map((item) => { const meta = statusMeta(item.status); const border = item.status === "compliant" ? "border-emerald-400 bg-emerald-400/10" : item.status === "non_compliant" ? "border-red-400 bg-red-400/15" : "border-amber-300 bg-amber-300/15"; return <div key={item.key} data-testid={`annotation-box-${item.key}`} title={item.field_name} className={`absolute rounded-md border-2 ${border} transition-all hover:z-10 hover:scale-[1.02]`} style={{ left: `${item.bbox.x}%`, top: `${item.bbox.y}%`, width: `${item.bbox.width}%`, height: `${item.bbox.height}%` }}><span className={`absolute -top-5 left-0 rounded-t-md px-1.5 py-0.5 text-[9px] font-bold text-white ${item.status === "compliant" ? "bg-emerald-600" : item.status === "non_compliant" ? "bg-red-600" : "bg-amber-600"}`}>{meta.label}</span></div>; })}<div data-testid="image-evidence-legend" className="absolute bottom-3 left-3 flex flex-wrap gap-2 rounded-lg bg-slate-950/75 px-3 py-2 text-[10px] font-semibold text-white backdrop-blur-sm"><span className="flex items-center gap-1.5"><i className="size-2 rounded-full bg-emerald-400" /> Pass</span><span className="flex items-center gap-1.5"><i className="size-2 rounded-full bg-amber-300" /> Review</span><span className="flex items-center gap-1.5"><i className="size-2 rounded-full bg-red-400" /> Violation</span></div></div></CardContent></Card><Card data-testid="declaration-details-card" className="border-slate-200 shadow-sm lg:col-span-5"><CardHeader className="border-b border-slate-100 pb-4"><CardTitle data-testid="declaration-details-title" className="font-heading text-lg font-bold">Declaration findings</CardTitle><p data-testid="declaration-details-description" className="mt-1 text-xs text-slate-500">Six required checks · verdicts from the configured LMPC rule engine</p></CardHeader><CardContent className="max-h-[600px] space-y-3 overflow-y-auto p-4 sm:p-5">{scan.declarations.map((item) => <DeclarationCard key={item.key} item={item} />)}<Button type="button" data-testid="declaration-report-button" className="mt-3 min-h-11 w-full gap-2 bg-blue-900 hover:bg-blue-800" onClick={onReport}><FileCheck2 className="size-4" /> Generate compliance report</Button></CardContent></Card></div></div>;
}

function ResultCount({ label, value, tone }: { label: string; value: number; tone: "green" | "amber" | "red" }) { const color = { green: "text-emerald-700 bg-emerald-50 border-emerald-100", amber: "text-amber-700 bg-amber-50 border-amber-100", red: "text-red-700 bg-red-50 border-red-100" }[tone]; return <div data-testid={`result-count-${label.toLowerCase()}`} className={`rounded-xl border px-3 py-2 ${color}`}><p data-testid={`result-count-label-${label.toLowerCase()}`} className="text-[10px] font-bold uppercase tracking-wider">{label}</p><p data-testid={`result-count-value-${label.toLowerCase()}`} className="mt-1 font-mono text-xl font-bold">{value}</p></div>; }

function DeclarationCard({ item }: { item: DeclarationResult }) { return <div data-testid={`declaration-card-${item.key}`} className="rounded-xl border border-slate-200 p-3 transition-all hover:border-blue-200 hover:shadow-sm"><div className="flex items-start gap-3"><div className={`mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg ${item.status === "compliant" ? "bg-emerald-50 text-emerald-600" : item.status === "non_compliant" ? "bg-red-50 text-red-600" : "bg-amber-50 text-amber-600"}`}>{item.status === "compliant" ? <Check className="size-4" /> : item.status === "non_compliant" ? <X className="size-4" /> : <AlertCircle className="size-4" />}</div><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center justify-between gap-2"><p data-testid={`declaration-name-${item.key}`} className="text-sm font-bold text-slate-800">{item.field_name}</p><StatusPill status={item.status} /></div><p data-testid={`declaration-value-${item.key}`} className="mt-2 break-words font-mono text-xs text-slate-600">{item.detected_value ?? "Not detected"}</p><div className="mt-3 rounded-lg bg-slate-50 p-2.5"><p data-testid={`declaration-reason-${item.key}`} className="text-xs leading-relaxed text-slate-600">{item.reason}</p><p data-testid={`declaration-rule-${item.key}`} className="mt-1.5 text-[10px] font-bold uppercase tracking-wide text-blue-700">{item.rule_code} · {item.requirement}</p></div></div></div></div>; }

function ReportView({ scan, remarks, setRemarks, onBack, onDownload, onSave, isSaving }: { scan: ScanRecord; remarks: string; setRemarks: (value: string) => void; onBack: () => void; onDownload: (format: "pdf" | "docx") => void; onSave: () => void; isSaving: boolean }) {
  return <><PageHeading eyebrow="Compliance report" title="Inspection report preview" description="Review the evidence summary, add an officer remark, and download an editable report pack for the case file." action={<button type="button" data-testid="report-back-button" onClick={onBack} className="inline-flex min-h-11 items-center gap-2 text-sm font-bold text-slate-500 hover:text-blue-900"><ArrowLeft className="size-4" /> Back to findings</button>} /><div className="grid gap-6 xl:grid-cols-[1fr_350px]"><Card data-testid="report-preview-card" className="border-slate-200 shadow-sm"><CardContent className="p-5 sm:p-8"><div className="border-b-2 border-blue-900 pb-5"><div className="flex items-start justify-between gap-4"><div className="flex items-center gap-3"><div data-testid="report-emblem" className="flex size-11 items-center justify-center rounded-xl bg-blue-900 text-white"><Scale className="size-5" /></div><div><p data-testid="report-department" className="text-[10px] font-bold uppercase tracking-[0.16em] text-blue-900">Government of India</p><p data-testid="report-ministry" className="text-sm font-bold text-slate-900">Department of Consumer Affairs</p></div></div><Badge data-testid="report-draft-badge" variant="outline" className="border-amber-200 bg-amber-50 text-amber-700">Draft for verification</Badge></div><div className="mt-6"><p data-testid="report-title-label" className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Legal Metrology Inspection Report</p><h3 data-testid="report-product-title" className="mt-1 font-heading text-2xl font-bold text-slate-900">{scan.product_name}</h3><p data-testid="report-product-meta" className="mt-2 text-xs text-slate-500">{scan.manufacturer} · {scan.category} · {scan.region}</p></div></div><div className="grid grid-cols-2 gap-4 border-b border-slate-200 py-5 sm:grid-cols-4"><ReportMeta label="Inspection ID" value={scan.id.slice(0, 8).toUpperCase()} /><ReportMeta label="Inspector" value={scan.inspector} /><ReportMeta label="Date" value={formatDate(scan.scanned_at)} /><ReportMeta label="Outcome" value={statusMeta(scan.status).label} /></div><div className="py-5"><p data-testid="report-findings-heading" className="mb-3 text-sm font-bold text-slate-900">Declaration findings</p><div className="overflow-hidden rounded-xl border border-slate-200"><div className="grid grid-cols-[1.2fr_0.7fr_1.4fr] gap-3 bg-slate-50 px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-slate-500"><span>Field</span><span>Status</span><span>Finding</span></div>{scan.declarations.map((item) => <div key={item.key} data-testid={`report-row-${item.key}`} className="grid grid-cols-[1.2fr_0.7fr_1.4fr] gap-3 border-t border-slate-100 px-3 py-3 text-xs"><span className="font-semibold text-slate-800">{item.field_name}</span><span><StatusPill status={item.status} /></span><span className="leading-relaxed text-slate-500">{item.reason}</span></div>)}</div></div><div className="rounded-xl border border-blue-100 bg-blue-50/50 p-4"><p data-testid="report-evidence-note" className="text-xs leading-relaxed text-slate-600"><strong className="text-blue-900">Evidence note:</strong> This prototype report includes the annotated package image and rule-linked OCR findings. A reviewer should confirm any marginal font-height or obscured address finding in person.</p></div></CardContent></Card><Card data-testid="report-actions-card" className="h-fit border-slate-200 shadow-sm"><CardHeader><CardTitle data-testid="report-actions-title" className="font-heading text-lg font-bold">Finalize report</CardTitle><p data-testid="report-actions-description" className="mt-1 text-xs leading-relaxed text-slate-500">Add context before the record is marked verified.</p></CardHeader><CardContent className="space-y-4"><label data-testid="report-remarks-label" htmlFor="report-remarks" className="text-xs font-bold text-slate-700">Inspector / officer remarks</label><textarea id="report-remarks" data-testid="report-remarks-input" value={remarks} onChange={(event) => setRemarks(event.target.value)} className="min-h-28 w-full resize-y rounded-xl border border-slate-200 bg-white p-3 text-sm outline-none transition-all placeholder:text-slate-400 focus:border-blue-500 focus:ring-3 focus:ring-blue-100" placeholder="Add a note for the case file..." /><Button type="button" data-testid="report-save-button" disabled={isSaving} className="min-h-11 w-full gap-2 bg-blue-900 hover:bg-blue-800" onClick={onSave}><CheckCircle2 className="size-4" /> {isSaving ? "Saving..." : "Save reviewer decision"}</Button><div className="border-t border-slate-100 pt-4"><p data-testid="report-download-label" className="mb-3 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-400">Export evidence pack</p><div className="grid grid-cols-2 gap-2"><Button type="button" data-testid="report-download-pdf" variant="outline" className="min-h-11 gap-2" onClick={() => onDownload("pdf")}><Download className="size-4" /> Mock PDF</Button><Button type="button" data-testid="report-download-docx" variant="outline" className="min-h-11 gap-2" onClick={() => onDownload("docx")}><Download className="size-4" /> Mock DOCX</Button></div></div></CardContent></Card></div></>;
}

function ReportMeta({ label, value }: { label: string; value: string }) { return <div data-testid={`report-meta-${label.toLowerCase().replaceAll(" ", "-")}`}><p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">{label}</p><p className="mt-1 truncate text-xs font-semibold text-slate-800">{value}</p></div>; }

function RepositoryView({ scans, search, setSearch, onOpenScan, role }: { scans: ScanRecord[]; search: string; setSearch: (value: string) => void; onOpenScan: (scan: ScanRecord) => void; role: Role }) {
  return <><PageHeading eyebrow={role === "reviewer" ? "Officer review queue" : "Inspection repository"} title={role === "reviewer" ? "Prioritise flagged findings" : "All inspection records"} description="Search product, manufacturer, category, region, or inspector to reopen evidence and review the case history." /><Card data-testid="repository-card" className="border-slate-200 shadow-sm"><CardContent className="p-4 sm:p-6"><div className="mb-5 flex flex-col gap-3 lg:flex-row"><div className="relative flex-1"><Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" /><Input data-testid="repository-search-input" value={search} onChange={(event) => setSearch(event.target.value)} className="h-11 pl-9" placeholder="Search product, manufacturer, region..." /></div><div className="flex gap-2"><button type="button" data-testid="repository-filter-button" onClick={() => toast.info("More filters are available in the production build")} className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-slate-200 px-3 text-sm font-semibold text-slate-600 hover:border-blue-300 hover:text-blue-900"><Filter className="size-4" /> Filters</button><select data-testid="repository-status-filter" className="min-h-11 rounded-lg border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-600 outline-none focus:border-blue-500"><option>All statuses</option><option>Violations</option><option>Compliant</option><option>Needs review</option></select></div></div><div className="overflow-x-auto"><table data-testid="repository-table" className="w-full min-w-[720px] border-separate border-spacing-0 text-left"><thead><tr className="bg-slate-50 text-[10px] font-bold uppercase tracking-wider text-slate-500"><th data-testid="repository-header-product" className="rounded-l-lg px-3 py-3">Product / manufacturer</th><th data-testid="repository-header-category" className="px-3 py-3">Category</th><th data-testid="repository-header-region" className="px-3 py-3">Region</th><th data-testid="repository-header-date" className="px-3 py-3">Scanned</th><th data-testid="repository-header-status" className="px-3 py-3">Status</th><th data-testid="repository-header-action" className="rounded-r-lg px-3 py-3">Action</th></tr></thead><tbody>{scans.map((scan) => <tr key={scan.id} data-testid={`repository-row-${scan.id}`} className="border-b border-slate-100 text-sm"><td className="border-b border-slate-100 px-3 py-4"><button type="button" data-testid={`repository-open-${scan.id}`} onClick={() => onOpenScan(scan)} className="text-left hover:text-blue-900"><p data-testid={`repository-product-${scan.id}`} className="font-bold text-slate-800">{scan.product_name}</p><p data-testid={`repository-manufacturer-${scan.id}`} className="mt-1 text-xs text-slate-500">{scan.manufacturer}</p></button></td><td data-testid={`repository-category-${scan.id}`} className="border-b border-slate-100 px-3 py-4 text-xs text-slate-600">{scan.category}</td><td data-testid={`repository-region-${scan.id}`} className="border-b border-slate-100 px-3 py-4 text-xs text-slate-600"><span className="inline-flex items-center gap-1"><MapPin className="size-3" />{scan.region}</span></td><td data-testid={`repository-date-${scan.id}`} className="border-b border-slate-100 px-3 py-4 text-xs text-slate-600">{formatDate(scan.scanned_at)}</td><td className="border-b border-slate-100 px-3 py-4"><StatusPill status={scan.status} /></td><td className="border-b border-slate-100 px-3 py-4"><Button type="button" data-testid={`repository-review-${scan.id}`} variant="ghost" size="sm" onClick={() => onOpenScan(scan)}>Review <ChevronRight className="size-3" /></Button></td></tr>)}</tbody></table></div><p data-testid="repository-result-count" className="mt-4 text-xs text-slate-400">Showing {scans.length} records · data refreshes from the enforcement API</p></CardContent></Card></>;
}

function AnalyticsView({ dashboard }: { dashboard: DashboardResponse }) {
  const chartColors = ["#1e3a8a", "#2563eb", "#d97706", "#dc2626"];
  return <><PageHeading eyebrow="National analytics" title="Where compliance breaks down" description="Use the pattern of violations to focus follow-up inspections, reviewer capacity, and manufacturer outreach." action={<Button type="button" data-testid="analytics-export-button" variant="outline" className="min-h-11 gap-2" onClick={() => toast.success("Analytics snapshot prepared")}><Download className="size-4" /> Export snapshot</Button>} /><div data-testid="analytics-summary-grid" className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4"><MetricCard label="Total scanned" value={String(dashboard.stats.total_scanned)} change="Across all regions" icon={ScanLine} tone="blue" /><MetricCard label="Violation rate" value={`${dashboard.stats.violation_rate}%`} change="Target < 15%" icon={AlertCircle} tone="red" /><MetricCard label="Pending reviews" value={String(dashboard.stats.pending_reviews)} change="14 due this week" icon={Flag} tone="amber" /><MetricCard label="Reports issued" value={String(dashboard.stats.reports_issued)} change="Verified case files" icon={FileCheck2} tone="green" /></div><div className="grid gap-6 lg:grid-cols-[1.35fr_0.65fr]"><Card data-testid="compliance-trend-card" className="border-slate-200 shadow-sm"><CardHeader><CardTitle data-testid="compliance-trend-title" className="font-heading text-lg font-bold">Compliance trend</CardTitle><p data-testid="compliance-trend-description" className="mt-1 text-xs text-slate-500">Monthly inspection outcomes</p></CardHeader><CardContent data-testid="compliance-trend-chart" className="h-[300px] px-2 sm:px-6"><ResponsiveContainer width="100%" height="100%"><LineChart data={dashboard.trend} margin={{ left: -20, right: 8, top: 12, bottom: 4 }}><CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" vertical={false} /><XAxis dataKey="month" tick={{ fontSize: 11, fill: "#64748b" }} axisLine={false} tickLine={false} /><YAxis tick={{ fontSize: 11, fill: "#64748b" }} axisLine={false} tickLine={false} /><Tooltip contentStyle={{ borderRadius: 12, border: "1px solid #e2e8f0", fontSize: 12 }} /><Line type="monotone" dataKey="compliant" name="Compliant" stroke="#16a34a" strokeWidth={3} dot={{ r: 3, fill: "#16a34a" }} /><Line type="monotone" dataKey="violations" name="Violations" stroke="#dc2626" strokeWidth={3} dot={{ r: 3, fill: "#dc2626" }} /></LineChart></ResponsiveContainer></CardContent></Card><Card data-testid="violation-breakdown-card" className="border-slate-200 shadow-sm"><CardHeader><CardTitle data-testid="violation-breakdown-title" className="font-heading text-lg font-bold">Top violation types</CardTitle><p data-testid="violation-breakdown-description" className="mt-1 text-xs text-slate-500">Findings requiring attention</p></CardHeader><CardContent data-testid="violation-breakdown-chart" className="h-[300px]"><ResponsiveContainer width="100%" height="100%"><BarChart data={dashboard.violation_types} layout="vertical" margin={{ left: 4, right: 18, top: 8, bottom: 8 }}><CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" horizontal={false} /><XAxis type="number" hide /><YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 10, fill: "#475569" }} axisLine={false} tickLine={false} /><Tooltip contentStyle={{ borderRadius: 12, border: "1px solid #e2e8f0", fontSize: 12 }} /><Bar dataKey="value" fill="#1e3a8a" radius={[0, 5, 5, 0]} barSize={18} /></BarChart></ResponsiveContainer></CardContent></Card></div><div className="mt-6 grid gap-6 lg:grid-cols-2"><Card data-testid="regions-card" className="border-slate-200 shadow-sm"><CardHeader><CardTitle data-testid="regions-title" className="font-heading text-lg font-bold">Region-wise workload</CardTitle><p data-testid="regions-description" className="mt-1 text-xs text-slate-500">Scans recorded by field region</p></CardHeader><CardContent data-testid="regions-chart" className="h-[260px]"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={dashboard.regions} dataKey="value" nameKey="name" innerRadius={58} outerRadius={90} paddingAngle={4}>{dashboard.regions.map((entry, index) => <Cell key={entry.name} fill={chartColors[index % chartColors.length]} />)}</Pie><Tooltip contentStyle={{ borderRadius: 12, border: "1px solid #e2e8f0", fontSize: 12 }} /></PieChart></ResponsiveContainer></CardContent></Card><Card data-testid="analytics-priority-card" className="border-slate-200 shadow-sm"><CardHeader><CardTitle data-testid="analytics-priority-title" className="font-heading text-lg font-bold">Action priorities</CardTitle><p data-testid="analytics-priority-description" className="mt-1 text-xs text-slate-500">Suggested focus from current data</p></CardHeader><CardContent className="space-y-3">{["Increase close-up captures for PDP font checks", "Review MRP inclusive-tax wording in staples", "Schedule follow-up in Delhi NCR clusters"].map((item, index) => <div key={item} data-testid={`analytics-priority-${index}`} className="flex gap-3 rounded-xl border border-slate-100 bg-slate-50 p-3"><span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-blue-900 text-[10px] font-bold text-white">{index + 1}</span><p data-testid={`analytics-priority-copy-${index}`} className="text-xs leading-relaxed text-slate-600">{item}</p></div>)}</CardContent></Card></div></>;
}

function RulesView({ rules, search, setSearch, role }: { rules: RuleItem[]; search: string; setSearch: (value: string) => void; role: Role }) {
  const displayRules = rules.length ? rules : [{ id: "fallback-rule", title: "Rules reference loading", rule_code: "—", requirement: "The reference library will appear when the compliance API is available.", min_font_height_mm: 0, mandatory: false, updated_at: "" }];
  return <><PageHeading eyebrow={role === "admin" ? "Admin-managed reference" : "Field reference library"} title="Rules at the point of inspection" description="Search the declaration requirement, rule code, and minimum font threshold while reviewing a label in the field." action={role === "admin" ? <Button type="button" data-testid="rules-add-button" className="min-h-11 gap-2 bg-blue-900 hover:bg-blue-800" onClick={() => toast.info("Rule editor is available as a prototype action")}> <BookOpen className="size-4" /> Add rule</Button> : null} /><div className="mb-5 max-w-xl"><div className="relative"><Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" /><Input data-testid="rules-search-input" value={search} onChange={(event) => setSearch(event.target.value)} className="h-11 pl-9" placeholder="Search by field, rule code, or requirement..." /></div></div><div data-testid="rules-list" className="grid gap-4 lg:grid-cols-2">{displayRules.map((rule) => <Card key={rule.id} data-testid={`rule-card-${rule.id}`} className="border-slate-200 shadow-sm"><CardContent className="p-5 sm:p-6"><div className="flex items-start justify-between gap-3"><div><p data-testid={`rule-code-${rule.id}`} className="text-[10px] font-bold uppercase tracking-[0.16em] text-blue-700">{rule.rule_code}</p><h3 data-testid={`rule-title-${rule.id}`} className="mt-1 font-heading text-lg font-bold text-slate-900">{rule.title}</h3></div>{rule.mandatory ? <Badge data-testid={`rule-mandatory-${rule.id}`} className="bg-red-50 text-red-700 hover:bg-red-50">Mandatory</Badge> : null}</div><p data-testid={`rule-requirement-${rule.id}`} className="mt-4 text-sm leading-relaxed text-slate-600">{rule.requirement}</p><div className="mt-5 flex items-center justify-between border-t border-slate-100 pt-4"><span data-testid={`rule-font-${rule.id}`} className="inline-flex items-center gap-2 text-xs font-semibold text-slate-500"><Scale className="size-4 text-blue-700" /> Min. font height <strong className="font-mono text-slate-900">{rule.min_font_height_mm ? `${rule.min_font_height_mm} mm` : "—"}</strong></span><span data-testid={`rule-updated-${rule.id}`} className="text-[10px] text-slate-400">Updated {rule.updated_at || "when API is connected"}</span></div></CardContent></Card>)}</div></>;
}

function UsersView() {
  const users = [{ name: "Aditi Rao", id: "INS-042", role: "Field Inspector", region: "Delhi NCR", status: "Active" }, { name: "Vivek Sharma", id: "REV-006", role: "Compliance Reviewer", region: "National", status: "Active" }, { name: "Meera Nair", id: "ADM-001", role: "Admin Officer", region: "National", status: "Active" }, { name: "Rohan Mehta", id: "INS-017", role: "Field Inspector", region: "Maharashtra", status: "Active" }];
  return <><PageHeading eyebrow="Administration" title="Users & access roles" description="Manage prototype workspaces and the regional assignment visible to each enforcement officer." action={<Button type="button" data-testid="invite-user-button" className="min-h-11 gap-2 bg-blue-900 hover:bg-blue-800" onClick={() => toast.info("Invite flow is mocked for this prototype")}><Users className="size-4" /> Add user</Button>} /><Card data-testid="users-table-card" className="border-slate-200 shadow-sm"><CardContent className="p-4 sm:p-6"><div className="mb-5 flex items-center justify-between"><div><p data-testid="users-count" className="font-heading text-lg font-bold text-slate-900">4 prototype accounts</p><p data-testid="users-description" className="mt-1 text-xs text-slate-500">Role selector sessions are clearly marked for demo use.</p></div><Badge data-testid="users-directory-status" variant="outline" className="border-emerald-200 bg-emerald-50 text-emerald-700">Directory synced</Badge></div><div className="overflow-x-auto"><table data-testid="users-table" className="w-full min-w-[620px] text-left"><thead><tr className="bg-slate-50 text-[10px] font-bold uppercase tracking-wider text-slate-500"><th className="rounded-l-lg px-3 py-3">Officer</th><th className="px-3 py-3">Role</th><th className="px-3 py-3">Region</th><th className="px-3 py-3">Status</th><th className="rounded-r-lg px-3 py-3">Access</th></tr></thead><tbody>{users.map((user) => <tr key={user.id} data-testid={`user-row-${user.id}`} className="border-b border-slate-100 text-sm"><td className="px-3 py-4"><p data-testid={`user-name-${user.id}`} className="font-bold text-slate-800">{user.name}</p><p data-testid={`user-id-${user.id}`} className="mt-1 font-mono text-[11px] text-slate-500">{user.id}</p></td><td data-testid={`user-role-${user.id}`} className="px-3 py-4 text-xs text-slate-600">{user.role}</td><td data-testid={`user-region-${user.id}`} className="px-3 py-4 text-xs text-slate-600">{user.region}</td><td data-testid={`user-status-${user.id}`} className="px-3 py-4"><Badge variant="outline" className="border-emerald-200 bg-emerald-50 text-emerald-700">{user.status}</Badge></td><td className="px-3 py-4"><button type="button" data-testid={`user-edit-${user.id}`} onClick={() => toast.info(`Editing ${user.name} is mocked`)} className="text-xs font-bold text-blue-900 hover:text-blue-600">Edit access</button></td></tr>)}</tbody></table></div></CardContent></Card></>;
}