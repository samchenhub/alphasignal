"use client";

import { useState } from "react";
import { StockChart } from "./components/StockChart";
import { NewsFeed } from "./components/NewsFeed";
import { AlertsPanel } from "./components/AlertsPanel";
import { SearchPanel } from "./components/SearchPanel";

const US_TICKERS = ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA", "META", "AMZN"];
const CN_TICKERS = ["600519", "000858", "300750"];

type Tab = "chart" | "news" | "alerts" | "search";

export default function Home() {
  const [selectedTicker, setSelectedTicker] = useState("AAPL");
  const [selectedMarket, setSelectedMarket] = useState<"US" | "CN">("US");
  const [activeTab, setActiveTab] = useState<Tab>("chart");

  const tickers = selectedMarket === "US" ? US_TICKERS : CN_TICKERS;

  return (
    <div className="space-y-6">
      {/* Ticker selector */}
      <div className="flex flex-wrap gap-2 items-center">
        <div className="flex rounded-lg border border-[#2a2d3e] overflow-hidden mr-2">
          {(["US", "CN"] as const).map((m) => (
            <button
              key={m}
              onClick={() => {
                setSelectedMarket(m);
                setSelectedTicker(m === "US" ? "AAPL" : "600519");
              }}
              className={`px-4 py-1.5 text-sm font-medium transition-colors ${
                selectedMarket === m
                  ? "bg-indigo-600 text-white"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              {m === "US" ? "🇺🇸 US" : "🇨🇳 A-Share"}
            </button>
          ))}
        </div>

        {tickers.map((t) => (
          <button
            key={t}
            onClick={() => setSelectedTicker(t)}
            className={`px-3 py-1 rounded text-sm font-mono transition-colors border ${
              selectedTicker === t
                ? "bg-indigo-600 border-indigo-500 text-white"
                : "border-[#2a2d3e] text-slate-400 hover:text-white hover:border-slate-500"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[#2a2d3e] pb-0">
        {(
          [
            { id: "chart", label: "Price & Sentiment" },
            { id: "news", label: "News Feed" },
            { id: "alerts", label: "Alerts" },
            { id: "search", label: "Search" },
          ] as { id: Tab; label: string }[]
        ).map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${
              activeTab === tab.id
                ? "border-indigo-500 text-white"
                : "border-transparent text-slate-500 hover:text-slate-300"
            }`}
          >
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
