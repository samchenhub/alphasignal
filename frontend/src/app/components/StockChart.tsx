"use client";

import { useEffect, useRef } from "react";
import useSWR from "swr";
import {
  ComposedChart,
  Line,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

interface PriceSentimentPoint {
  timestamp: string;
  close_price: number | null;
  sentiment_score: number | null;
  confidence: number | null;
}

interface Props {
  ticker: string;
  market: "US" | "CN";
}

function SentimentBadge({ score }: { score: number }) {
  const label =
    score > 0.3 ? "Bullish" : score < -0.3 ? "Bearish" : "Neutral";
  const color =
    score > 0.3
      ? "text-green-400 bg-green-400/10"
      : score < -0.3
        ? "text-red-400 bg-red-400/10"
        : "text-gray-400 bg-gray-400/10";
  return (
    <span className={`text-xs px-2 py-0.5 rounded font-medium ${color}`}>
      {label} ({score > 0 ? "+" : ""}
      {score.toFixed(2)})
    </span>
  );
}

export function StockChart({ ticker, market }: Props) {
  const { data, error, isLoading } = useSWR<PriceSentimentPoint[]>(
    `/api/v1/sentiment/${ticker}/price-correlation?days=30`,
    fetcher,
    { refreshInterval: 60_000 }
  );

  const { data: sentimentData } = useSWR<{ sentiment_score: number }[]>(
    `/api/v1/sentiment/${ticker}?days=1`,
    fetcher,
    { refreshInterval: 30_000 }
  );

  const latestSentiment =
    sentimentData && sentimentData.length > 0
      ? sentimentData[0].sentiment_score
      : null;

  if (isLoading) {
    return (
      <div className="bg-[#1a1d2e] border border-[#2a2d3e] rounded-xl h-96 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-slate-500">
          <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm">Loading chart data…</span>
        </div>
      </div>
    );
  }

  if (error || !data || data.length === 0) {
    return (
      <div className="bg-[#1a1d2e] border border-[#2a2d3e] rounded-xl h-96 flex items-center justify-center">
        <div className="flex flex-col items-center gap-2 text-slate-500">
          <span className="text-4xl">📊</span>
          <p className="font-medium text-slate-400">No price data yet for {ticker}</p>
          <p className="text-xs text-slate-600">Price data syncs hourly</p>
        </div>
      </div>
    );
  }

  const chartData = data.map((d) => ({
    date: new Date(d.timestamp).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    }),
    price: d.close_price,
    sentiment: d.sentiment_score !== null ? d.sentiment_score * 100 : null, // scale to -100..100 for visual
    rawSentiment: d.sentiment_score,
  }));

  const sentimentColor = (value: number | null) => {
    if (value === null) return "#6b7280";
    if (value > 30) return "#22c55e";
    if (value < -30) return "#ef4444";
    return "#6b7280";
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-2xl font-bold text-white">{ticker}</h2>
              <span className="text-xs text-slate-500 bg-[#2a2d3e] px-2 py-0.5 rounded font-mono">
                {market}
              </span>
            </div>
            {latestSentiment !== null && (
              <div className="flex items-center gap-2 mt-1">
                <SentimentBadge score={latestSentiment} />
                <span className="text-xs text-slate-500">latest signal</span>
              </div>
            )}
          </div>
        </div>
        <div className="text-right">
          <p className="text-xs text-slate-500">Price + Sentiment · 30 days</p>
          <p className="text-xs text-slate-600 mt-0.5">Green bars = bullish · Red bars = bearish</p>
        </div>
      </div>

      {/* Chart */}
      <div className="bg-[#1a1d2e] rounded-xl border border-[#2a2d3e] p-4">
        <ResponsiveContainer width="100%" height={380}>
          <ComposedChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3e" />
            <XAxis
              dataKey="date"
              tick={{ fill: "#64748b", fontSize: 11 }}
              axisLine={{ stroke: "#2a2d3e" }}
            />
            <YAxis
              yAxisId="price"
              orientation="left"
              tick={{ fill: "#64748b", fontSize: 11 }}
              axisLine={{ stroke: "#2a2d3e" }}
              tickFormatter={(v) => `$${v}`}
            />
            <YAxis
              yAxisId="sentiment"
              orientation="right"
              domain={[-100, 100]}
              tick={{ fill: "#64748b", fontSize: 11 }}
              axisLine={{ stroke: "#2a2d3e" }}
              tickFormatter={(v) => `${v > 0 ? "+" : ""}${v}`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#1a1d2e",
                border: "1px solid #2a2d3e",
                borderRadius: "8px",
                color: "#e2e8f0",
              }}
              formatter={(value: number, name: string) => {
                if (name === "price") return [`$${value?.toFixed(2)}`, "Price"];
                if (name === "sentiment")
                  return [
                    `${(value / 100).toFixed(2)} (${value > 0 ? "+" : ""}${value.toFixed(0)})`,
                    "Sentiment",
                  ];
                return [value, name];
              }}
            />
            <Legend
              wrapperStyle={{ color: "#94a3b8", fontSize: 12 }}
            />
            <Line
              yAxisId="price"
              type="monotone"
              dataKey="price"
              stroke="#6366f1"
              strokeWidth={2}
              dot={false}
              name="price"
            />
            <Bar
              yAxisId="sentiment"
              dataKey="sentiment"
              name="sentiment"
              opacity={0.7}
              radius={[2, 2, 0, 0]}
            >
              {chartData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={
                    entry.sentiment === null
                      ? "#6b7280"
                      : entry.sentiment > 30
                        ? "#22c55e"
                        : entry.sentiment < -30
                          ? "#ef4444"
                          : "#6b7280"
                  }
                />
              ))}
            </Bar>
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <p className="text-xs text-slate-600">
        Sentiment bars represent the daily average LLM sentiment score (×100) from analyzed news articles.
        Green = bullish, red = bearish.
      </p>
    </div>
  );
}
