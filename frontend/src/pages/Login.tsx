import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Eye, EyeOff, LockKeyhole, Scale, ShieldCheck } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiPost } from "@/lib/api";
import { beginSession } from "@/lib/session";
import type { User } from "@/lib/types";

const demoAccounts = [
  { role: "Inspector", email: "inspector@lmchecker.gov.in", password: "Inspector@123" },
  { role: "Admin", email: "admin@lmchecker.gov.in", password: "Admin@123" },
  { role: "Consumer", email: "consumer@example.in", password: "Consumer@123" },
];

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState(demoAccounts[0].email);
  const [password, setPassword] = useState(demoAccounts[0].password);
  const [showPassword, setShowPassword] = useState(false);
  const login = useMutation({
    mutationFn: () => apiPost<User>("/auth/login", { email, password }),
    onSuccess: (user) => { beginSession(user); toast.success(`Welcome, ${user.name}`); navigate("/"); },
    onError: () => toast.error("Sign-in failed", { description: "Check the email and password and try again." }),
  });
  return <div data-testid="login-page" className="min-h-svh bg-slate-50 text-slate-900">
    <div data-testid="login-government-banner" className="flex h-12 items-center justify-between bg-[#0f172a] px-4 text-white sm:px-8"><span className="flex items-center gap-2 text-[11px] font-semibold tracking-wide text-slate-200"><ShieldCheck className="size-4 text-blue-300" /> GOVERNMENT OF INDIA <span className="hidden text-slate-400 sm:inline">/ Department of Consumer Affairs</span></span><span className="text-[10px] font-semibold uppercase tracking-wider text-emerald-300">Secure access portal</span></div>
    <main className="mx-auto grid min-h-[calc(100svh-48px)] max-w-6xl items-center gap-10 px-4 py-10 lg:grid-cols-[1.1fr_0.9fr] lg:px-8">
      <section data-testid="login-introduction" className="hidden lg:block"><div className="mb-6 flex size-14 items-center justify-center rounded-2xl bg-blue-900 text-white shadow-xl shadow-blue-900/20"><Scale className="size-7" /></div><p data-testid="login-eyebrow" className="text-xs font-bold uppercase tracking-[0.18em] text-blue-700">Legal Metrology Enforcement Portal</p><h1 data-testid="login-title" className="mt-4 max-w-xl font-heading text-5xl font-extrabold leading-[1.02] tracking-tight text-slate-900">Trusted label checks for Indian packaged commodities.</h1><p data-testid="login-description" className="mt-5 max-w-lg text-base leading-relaxed text-slate-600">Secure Inspector, Admin and Consumer workspaces for multi-face evidence, OCR extraction, rule-by-rule validation and report generation.</p></section>
      <Card data-testid="login-card" className="border-slate-200 bg-white shadow-2xl shadow-slate-900/10"><CardContent className="p-6 sm:p-8"><div className="mb-7"><div className="mb-4 flex size-11 items-center justify-center rounded-xl bg-blue-50 text-blue-900 lg:hidden"><Scale className="size-5" /></div><p data-testid="login-card-eyebrow" className="text-[10px] font-bold uppercase tracking-[0.18em] text-blue-700">Authorized access</p><h2 data-testid="login-card-title" className="mt-2 font-heading text-3xl font-bold tracking-tight">Sign in to your workspace</h2><p data-testid="login-card-description" className="mt-2 text-sm text-slate-500">Your account controls which inspections and review tools you can access.</p></div>
        <form data-testid="login-form" className="space-y-4" onSubmit={(event) => { event.preventDefault(); login.mutate(); }}><label data-testid="login-email-label" className="block text-xs font-bold text-slate-700">Email address<Input data-testid="login-email-input" className="mt-2 h-11" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} /></label><label data-testid="login-password-label" className="block text-xs font-bold text-slate-700">Password<div className="relative mt-2"><Input data-testid="login-password-input" className="h-11 pr-11" type={showPassword ? "text" : "password"} autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} /><button type="button" data-testid="login-password-toggle" onClick={() => setShowPassword((value) => !value)} className="absolute right-1 top-1 flex size-9 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-blue-900">{showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}</button></div></label><Button data-testid="login-submit-button" type="submit" disabled={login.isPending} className="min-h-11 w-full gap-2 bg-blue-900 hover:bg-blue-800"><LockKeyhole className="size-4" />{login.isPending ? "Signing in..." : "Secure sign in"}</Button></form>
        <div data-testid="demo-account-list" className="mt-7 border-t border-slate-100 pt-5"><p data-testid="demo-account-title" className="mb-3 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-400">Demo credentials</p><div className="grid gap-2">{demoAccounts.map((account) => <button key={account.role} type="button" data-testid={`login-demo-${account.role.toLowerCase()}`} onClick={() => { setEmail(account.email); setPassword(account.password); }} className="flex min-h-11 items-center justify-between rounded-xl border border-slate-200 px-3 text-left transition-colors hover:border-blue-300 hover:bg-blue-50"><span className="text-xs font-bold text-slate-700">{account.role}</span><span className="font-mono text-[10px] text-slate-500">{account.email}</span></button>)}</div></div>
      </CardContent></Card>
    </main>
  </div>;
}