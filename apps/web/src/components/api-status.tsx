"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { API_BASE_URL, ApiMode, getMode } from "@/lib/api";

type StatusState =
  | { kind: "loading" }
  | { kind: "ok"; mode: ApiMode }
  | { kind: "offline"; message: string };

export function ApiStatus() {
  const [state, setState] = useState<StatusState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    getMode()
      .then((mode) => {
        if (!cancelled) setState({ kind: "ok", mode });
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setState({
            kind: "offline",
            message:
              err instanceof Error
                ? err.message
                : `TasteOS API unreachable at ${API_BASE_URL}`,
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Card className="api-status-card border-[color:var(--line)] bg-[color:rgba(251,250,246,0.72)] shadow-none">
      <CardHeader className="pb-2">
        <CardTitle className="font-[family-name:var(--font-display)] text-xl tracking-tight">
          API connectivity
        </CardTitle>
        <CardDescription className="text-[color:var(--ink-soft)]">
          Live check against{" "}
          <code className="text-xs">{API_BASE_URL}</code>
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-wrap items-center gap-3">
        {state.kind === "loading" && (
          <Badge variant="secondary">Checking…</Badge>
        )}
        {state.kind === "ok" && (
          <>
            <Badge className="bg-[color:var(--copper)] text-white hover:bg-[color:var(--copper)]">
              Connected
            </Badge>
            <Badge variant="outline">{state.mode.label || state.mode.mode}</Badge>
            <span className="text-sm text-[color:var(--ink-soft)]">
              {state.mode.qloo_key_configured
                ? "Qloo key present (server-side)"
                : "Qloo key not configured — demo mode is fine for local setup"}
            </span>
          </>
        )}
        {state.kind === "offline" && (
          <>
            <Badge variant="destructive">Offline</Badge>
            <span className="text-sm text-[color:var(--error)]">
              {state.message}
            </span>
          </>
        )}
      </CardContent>
    </Card>
  );
}
