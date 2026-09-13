import { apiGet, apiPost } from "@/lib/api";
import { queryClient } from "@/lib/queryClient";
import type { User } from "@/lib/types";

export const sessionQueryKey = ["session"] as const;
export const fetchSession = () => apiGet<User>("/auth/me");

export function beginSession(user: User): void {
  queryClient.clear();
  queryClient.setQueryData(sessionQueryKey, user);
}

export async function endSession(redirectTo: string = "/login"): Promise<void> {
  try {
    await apiPost<void>("/auth/logout");
  } finally {
    queryClient.clear();
    window.location.assign(redirectTo);
  }
}