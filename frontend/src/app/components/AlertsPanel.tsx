"use client";

import useSWR from "swr";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const fetcher = (url: string) => fetch(url).then((r) => r.json());

interface AlertItem {
  id: string;
  ticker: string;
  alert_type: string;
  message: string;
  triggered_at: string;
  is_sent: boolean;
}

interface Props {
  ticker?: string;
}

export function AlertsPanel({ ticker }: Props) {
  const url = ticker
    ? `${API}/api/v1/alerts/?days=7&ticker=${ticker}`
    : `${API}/api/v1/alerts/?days=7`;

  const { data, isLoading } = useSWR<AlertItem[]>(url, fetcher, {
    refreshInterval: 30_000,
  });

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-16 bg-[#1a1d2e] rounded-xl animate-pulse" />
        ))}
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="text-center py-16 text-slate-500">
        <p className="text-3xl mb-3">🔔</p>
        <p>No extreme sentiment alerts{ticker ? ` for ${ticker}` : ""}</p>
        <p className="text-xs mt-1">
          Alerts fire when |score| &gt; 0.85 and confidence &gt; 90%
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {data.map((alert) => {
        const isBull = alert.alert_type === "extreme_positive";
        return (
          <div
            key={alert.id}
            className={`border rounded-xl p-4 ${
              isBull
                ? "border-green-500/30 bg-green-500/5"
                : "border-red-500/30 bg-red-500/5"
            }`}
          >
            <div className="flex items-start gap-3">
              <span className="text-xl">{isBull ? "🚀" : "⚠️"}</span>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span
                    className={`text-xs font-semibold px-2 py-0.5 rounded font-mono ${
                      isBull
                        ? "text-green-400 bg-green-400/10"
                        : "text-red-400 bg-red-400/10"
                    }`}
                  >
                    {alert.ticker}
                  </span>
                  <span
                    className={`text-xs ${
                      isBull ? "text-green-500" : "text-red-500"
                    }`}
                  >
                    {isBull ? "EXTREME BULLISH" : "EXTREME BEARISH"}
                  </span>
                </div>
                <p className="text-sm text-slate-300 mt-1">{alert.message}</p>
                <p className="text-xs text-slate-600 mt-1">
                  {new Date(alert.triggered_at).toLocaleString()}
                </p>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
