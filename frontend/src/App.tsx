import { useQuery } from "@tanstack/react-query";
import { Navigate, Route, Routes } from "react-router-dom";

import { fetchSession, sessionQueryKey } from "@/lib/session";
import Home from "@/pages/Home";
import Login from "@/pages/Login";

export default function App() {
  const session = useQuery({ queryKey: sessionQueryKey, queryFn: fetchSession, retry: false });
  if (session.isLoading) return <div data-testid="session-loading" className="grid min-h-svh place-items-center bg-slate-50 text-sm font-semibold text-slate-500">Checking secure session...</div>;
  return <Routes>
    <Route path="/login" element={session.data ? <Navigate to="/" replace /> : <Login />} />
    <Route path="*" element={session.data ? <Home user={session.data} /> : <Navigate to="/login" replace />} />
  </Routes>;
}