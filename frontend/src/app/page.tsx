"use client";

import { useState } from "react";
import useSWR from "swr";
import { StockChart } from "./components/StockChart";
import { NewsFeed } from "./components/NewsFeed";
import { AlertsPanel } from "./components/AlertsPanel";
import { SearchPanel } from "./components/SearchPanel";

const US_TICKERS = ["AMZN", "NVDA", "AAPL", "MSFT", "GOOGL", "TSLA", "META", "GS", "MS", "ADBE", "NFLX", "DIS", "AMD", "INTC"];
const CN_TICKERS = ["600519", "000858", "300750"];

type Tab = "chart" | "news" | "alerts" | "search";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-[#1a1d2e] border border-[#2a2d3e] rounded-xl px-5 py-4 flex flex-col gap-1">
      <span className="text-xs text-slate-500 uppercase tracking-wider font-medium">{label}</span>
      <span className="text-2xl font-semibold text-white">{value}</span>
      {sub && <span className="text-xs text-slate-500">{sub}</span>}
    </div>
  );
}

export default function Home() {
  const [selectedTicker, setSelectedTicker] = useState("AMZN");
  const [selectedMarket, setSelectedMarket] = useState<"US" | "CN">("US");
  const [activeTab, setActiveTab] = useState<Tab>("chart");

  const tickers = selectedMarket === "US" ? US_TICKERS : CN_TICKERS;

  const { data: stats } = useSWR<Record<string, number>>(
    "/api/v1/admin/stats",
    fetcher,
    { refreshInterval: 60_000 }
  );

  return (
    <div className="space-y-6">
      {/* Stats overview */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard
          label="Articles Analyzed"
          value={stats?.analysis_results ?? "—"}
          sub="LLM-processed"
        />
        <StatCard
          label="Articles Ingested"
          value={stats?.articles ?? "—"}
          sub="from RSS + yfinance"
        />
        <StatCard
          label="Price Data Points"
          value={stats?.stock_prices ?? "—"}
          sub="daily OHLCV"
        />
        <StatCard
          label="Active Alerts"
          value={stats?.alerts ?? "—"}
          sub="|score| > 0.85"
        />
      </div>

      {/* Market + Ticker selector */}
      <div className="bg-[#1a1d2e] border border-[#2a2d3e] rounded-xl p-4">
        <div className="flex items-center gap-3 mb-3">
          <span className="text-xs text-slate-500 uppercase tracking-wider font-medium">Market</span>
          <div className="flex rounded-lg border border-[#2a2d3e] overflow-hidden">
            {(["US", "CN"] as const).map((m) => (
              <button
                key={m}
                onClick={() => {
                  setSelectedMarket(m);
                  setSelectedTicker(m === "US" ? "AMZN" : "600519");
                }}
                className={`px-4 py-1.5 text-xs font-semibold transition-colors ${
                  selectedMarket === m
                    ? "bg-indigo-600 text-white"
                    : "text-slate-400 hover:text-white hover:bg-[#2a2d3e]"
                }`}
              >
                {m === "US" ? "🇺🇸 US" : "🇨🇳 A-Share"}
              </button>
            ))}
          </div>
        </div>

        {/* Scrollable ticker row */}
        <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
          {tickers.map((t) => (
            <button
              key={t}
              onClick={() => setSelectedTicker(t)}
              className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium whitespace-nowrap transition-all border ${
                selectedTicker === t
                  ? "bg-indigo-600 border-indigo-500 text-white shadow-lg shadow-indigo-500/20"
                  : "border-[#2a2d3e] text-slate-400 hover:text-white hover:border-slate-500 hover:bg-[#2a2d3e]"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[#2a2d3e]">
        {(
          [
            { id: "chart", label: "Price & Sentiment", icon: "📈" },
            { id: "news", label: "News Feed", icon: "📰" },
            { id: "alerts", label: "Alerts", icon: "🔔" },
            { id: "search", label: "Search", icon: "🔍" },
          ] as { id: Tab; label: string; icon: string }[]
        ).map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px flex items-center gap-1.5 ${
              activeTab === tab.id
                ? "border-indigo-500 text-white"
                : "border-transparent text-slate-500 hover:text-slate-300"
            }`}
          >
            <span className="text-xs">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div>
        {activeTab === "chart" && (
          <StockChart ticker={selectedTicker} market={selectedMarket} />
        )}
        {activeTab === "news" && (
          <NewsFeed ticker={selectedTicker} market={selectedMarket} />
        )}
        {activeTab === "alerts" && <AlertsPanel ticker={selectedTicker} />}
        {activeTab === "search" && <SearchPanel market={selectedMarket} />}
      </div>
    </div>
  );
}
