// Session 52: 后端 health 探测 — 暴露 ok/error/loading 三态
// 后续 S54+ 把这个 hook 抽到 src/app/hooks/
import { useEffect, useState } from "react";
import { apiClient, ApiError } from "../../app/apiClient";

export type HealthState =
  | { status: "loading" }
  | { status: "ok"; payload: unknown; latencyMs: number }
  | { status: "error"; message: string; statusCode?: number };

export function useHealth(): HealthState {
  const [state, setState] = useState<HealthState>({ status: "loading" });

  useEffect(() => {
    const ctrl = new AbortController();
    const t0 = performance.now();
    apiClient
      .get<{ status?: string; phase?: string }>("/health", { signal: ctrl.signal })
      .then((payload) => {
        setState({
          status: "ok",
          payload,
          latencyMs: Math.round(performance.now() - t0),
        });
      })
      .catch((err: unknown) => {
        if (ctrl.signal.aborted) return;
        if (err instanceof ApiError) {
          setState({
            status: "error",
            message: err.message,
            statusCode: err.status,
          });
        } else if (err instanceof Error) {
          setState({ status: "error", message: err.message });
        } else {
          setState({ status: "error", message: "unknown error" });
        }
      });
    return () => ctrl.abort();
  }, []);

  return state;
}
