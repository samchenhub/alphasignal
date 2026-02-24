"use client";

import { useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface TradeEntry {
  entry_date: string;
  exit_date: string;
  entry_price: number;
  exit_price: number;
  pnl_pct: number;
  direction: string;
}

interface BacktestMetrics {
  total_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
  total_trades: number;
}

interface BacktestResult {
  strategy_id: string;
  ticker: string;
  direction: string;
  parsed_strategy: {
    entry: { operator: string; threshold: number };
    exit: { holding_days: number };
  };
  metrics: BacktestMetrics;
  equity_curve: number[];
  trade_log: TradeEntry[];
  warning?: string;
}

interface Props {
  ticker: string;
}

const EXAMPLE_STRATEGIES = [
  "When sentiment drops below -0.6, go long and hold for 5 days",
  "Short the stock when sentiment exceeds 0.7, cover after 3 days",
  "Buy when sentiment score is below -0.5, exit after 7 trading days",
];

function MetricCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="bg-[#0f1117] border border-[#2a2d3e] rounded-xl px-4 py-3 flex flex-col gap-1">
      <span className="text-xs text-slate-500 uppercase tracking-wider font-medium">
        {label}
      </span>
      <span className={`text-xl font-semibold ${color ?? "text-white"}`}>
        {value}
      </span>
    </div>
  );
}

export function BacktestPanel({ ticker }: Props) {
  const [strategy, setStrategy] = useState("");
  const [selectedTicker, setSelectedTicker] = useState(ticker);
  const [startDate, setStartDate] = useState(() => {
    const d = new Date();
    d.setFullYear(d.getFullYear() - 1);
    return d.toISOString().split("T")[0];
  });
  const [endDate] = useState(() => new Date().toISOString().split("T")[0]);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleRun() {
    if (!strategy.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch("/api/v1/backtest/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          natural_language: strategy,
          ticker: selectedTicker,
          start_date: startDate,
          end_date: endDate,
        }),
      });

      let data: Record<string, unknown> = {};
      try {
        data = await res.json();
      } catch {
        setError(`Server error (${res.status}). Please try again.`);
        return;
      }

      if (!res.ok) {
        const detail = data.detail;
        const msg =
          typeof detail === "string"
            ? detail
            : Array.isArray(detail)
              ? (detail[0] as { msg?: string })?.msg ?? "Validation error"
              : `Request failed (${res.status})`;
        setError(msg);
      } else {
        setResult(data as unknown as BacktestResult);
      }
    } catch (err) {
      setError(`Network error: ${err instanceof Error ? err.message : "Could not reach server"}`);
    } finally {
      setLoading(false);
    }
  }

  const equityChartData = result?.equity_curve.map((v, i) => ({
    trade: i,
    equity: v,
  }));

  const totalReturnPct = result
    ? (result.metrics.total_return * 100).toFixed(2)
    : null;
  const returnColor = result
    ? result.metrics.total_return >= 0
      ? "text-green-400"
      : "text-red-400"
    : undefined;

  return (
    <div className="space-y-6">
      {/* Input panel */}
      <div className="bg-[#1a1d2e] border border-[#2a2d3e] rounded-xl p-5 space-y-4">
        <div>
          <h2 className="text-lg font-semibold text-white mb-1">
            Natural Language Backtest
          </h2>
          <p className="text-xs text-slate-500">
            Describe a sentiment-based strategy in plain English. The AI will
            parse it and simulate it against historical data.
          </p>
        </div>

        {/* Strategy input */}
        <div className="space-y-1.5">
          <label className="text-xs text-slate-400 font-medium">
            Strategy Description
          </label>
          <textarea
            className="w-full bg-[#0f1117] border border-[#2a2d3e] rounded-lg px-3 py-2.5 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-indigo-500 resize-none"
            rows={3}
            placeholder='e.g. "When AMZN sentiment drops below -0.6, go long. Exit after 5 trading days."'
            value={strategy}
            onChange={(e) => setStrategy(e.target.value)}
          />
          {/* Example chips */}
          <div className="flex flex-wrap gap-1.5 pt-1">
            {EXAMPLE_STRATEGIES.map((ex) => (
              <button
                key={ex}
                onClick={() => setStrategy(ex)}
                className="text-xs px-2 py-0.5 rounded-md bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 hover:bg-indigo-500/20 transition-colors"
              >
                {ex}
              </button>
            ))}
          </div>
        </div>

        {/* Ticker + date range */}
        <div className="flex flex-wrap gap-3 items-end">
          <div className="space-y-1">
            <label className="text-xs text-slate-400 font-medium">Ticker</label>
            <input
              className="bg-[#0f1117] border border-[#2a2d3e] rounded-lg px-3 py-1.5 text-sm text-slate-200 font-mono focus:outline-none focus:border-indigo-500 w-24 uppercase"
              value={selectedTicker}
              onChange={(e) => setSelectedTicker(e.target.value.toUpperCase())}
              maxLength={10}
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-slate-400 font-medium">
              Start Date
            </label>
            <input
              type="date"
              className="bg-[#0f1117] border border-[#2a2d3e] rounded-lg px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-slate-400 font-medium">
              End Date
            </label>
            <input
              type="date"
              className="bg-[#0f1117] border border-[#2a2d3e] rounded-lg px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
              value={endDate}
              readOnly
            />
          </div>

          <button
            onClick={handleRun}
            disabled={loading || !strategy.trim()}
            className="px-5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-semibold transition-colors flex items-center gap-2"
          >
            {loading ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Running…
              </>
            ) : (
              <>⚡ Run Backtest</>
            )}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-4">
          {/* Parsed strategy info */}
          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
            <span className="text-slate-500">Parsed as:</span>
            <span className="font-mono bg-[#1a1d2e] border border-[#2a2d3e] px-2 py-0.5 rounded">
              {result.direction.toUpperCase()} {result.ticker}
            </span>
            <span>when sentiment</span>
            <span className="font-mono bg-[#1a1d2e] border border-[#2a2d3e] px-2 py-0.5 rounded">
              {result.parsed_strategy.entry.operator}{" "}
              {result.parsed_strategy.entry.threshold}
            </span>
            <span>hold</span>
            <span className="font-mono bg-[#1a1d2e] border border-[#2a2d3e] px-2 py-0.5 rounded">
              {result.parsed_strategy.exit.holding_days} days
            </span>
          </div>

          {result.warning && (
            <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-xl px-4 py-2 text-xs text-yellow-400">
              ⚠ {result.warning}
            </div>
          )}

          {/* Metrics cards */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            <MetricCard
              label="Total Return"
              value={`${result.metrics.total_return >= 0 ? "+" : ""}${totalReturnPct}%`}
              color={returnColor}
            />
            <MetricCard
              label="Sharpe Ratio"
              value={result.metrics.sharpe_ratio.toFixed(2)}
              color={
                result.metrics.sharpe_ratio > 1
                  ? "text-green-400"
                  : result.metrics.sharpe_ratio < 0
                    ? "text-red-400"
                    : "text-white"
              }
            />
            <MetricCard
              label="Max Drawdown"
              value={`${(result.metrics.max_drawdown * 100).toFixed(1)}%`}
              color="text-red-400"
            />
            <MetricCard
              label="Win Rate"
              value={`${(result.metrics.win_rate * 100).toFixed(0)}%`}
              color={
                result.metrics.win_rate >= 0.5
                  ? "text-green-400"
                  : "text-red-400"
              }
            />
            <MetricCard
              label="Total Trades"
              value={String(result.metrics.total_trades)}
            />
          </div>

          {/* Equity curve */}
          {result.equity_curve.length > 1 && (
            <div className="bg-[#1a1d2e] border border-[#2a2d3e] rounded-xl p-4">
              <p className="text-xs text-slate-500 mb-3 font-medium uppercase tracking-wider">
                Equity Curve — Starting $10,000
              </p>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={equityChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3e" />
                  <XAxis
                    dataKey="trade"
                    tick={{ fill: "#64748b", fontSize: 11 }}
                    axisLine={{ stroke: "#2a2d3e" }}
                    label={{
                      value: "Trade #",
                      position: "insideBottom",
                      offset: -2,
                      fill: "#64748b",
                      fontSize: 11,
                    }}
                  />
                  <YAxis
                    tick={{ fill: "#64748b", fontSize: 11 }}
                    axisLine={{ stroke: "#2a2d3e" }}
                    tickFormatter={(v) => `$${v.toLocaleString()}`}
                    width={80}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1a1d2e",
                      border: "1px solid #2a2d3e",
                      borderRadius: "8px",
                      color: "#e2e8f0",
                    }}
                    formatter={(v: number) => [
                      `$${v.toLocaleString(undefined, { minimumFractionDigits: 2 })}`,
                      "Portfolio",
                    ]}
                    labelFormatter={(l) => `After trade ${l}`}
                  />
                  <Line
                    type="monotone"
                    dataKey="equity"
                    stroke={
                      result.metrics.total_return >= 0 ? "#22c55e" : "#ef4444"
                    }
                    strokeWidth={2}
                    dot={result.equity_curve.length <= 30}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Trade log table */}
          {result.trade_log.length > 0 && (
            <div className="bg-[#1a1d2e] border border-[#2a2d3e] rounded-xl overflow-hidden">
              <div className="px-4 py-3 border-b border-[#2a2d3e]">
                <p className="text-xs text-slate-500 font-medium uppercase tracking-wider">
                  Trade Log
                </p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-[#2a2d3e] text-slate-500">
                      <th className="px-4 py-2 text-left font-medium">#</th>
                      <th className="px-4 py-2 text-left font-medium">
                        Entry Date
                      </th>
                      <th className="px-4 py-2 text-left font-medium">
                        Exit Date
                      </th>
                      <th className="px-4 py-2 text-right font-medium">
                        Entry Price
                      </th>
                      <th className="px-4 py-2 text-right font-medium">
                        Exit Price
                      </th>
                      <th className="px-4 py-2 text-right font-medium">
                        P&L
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.trade_log.map((trade, i) => (
                      <tr
                        key={i}
                        className="border-b border-[#2a2d3e]/50 hover:bg-[#2a2d3e]/30"
                      >
                        <td className="px-4 py-2 text-slate-500">{i + 1}</td>
                        <td className="px-4 py-2 font-mono text-slate-300">
                          {trade.entry_date}
                        </td>
                        <td className="px-4 py-2 font-mono text-slate-300">
                          {trade.exit_date}
                        </td>
                        <td className="px-4 py-2 text-right font-mono text-slate-300">
                          ${trade.entry_price.toFixed(2)}
                        </td>
                        <td className="px-4 py-2 text-right font-mono text-slate-300">
                          ${trade.exit_price.toFixed(2)}
                        </td>
                        <td
                          className={`px-4 py-2 text-right font-mono font-medium ${
                            trade.pnl_pct >= 0
                              ? "text-green-400"
                              : "text-red-400"
                          }`}
                        >
                          {trade.pnl_pct >= 0 ? "+" : ""}
                          {trade.pnl_pct.toFixed(2)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Empty state */}
      {!result && !loading && !error && (
        <div className="text-center py-16 text-slate-600">
          <p className="text-4xl mb-3">⚡</p>
          <p className="font-medium text-slate-500">
            Enter a strategy above and click Run Backtest
          </p>
          <p className="text-xs mt-1">
            Backtests run against historical sentiment + price data
          </p>
        </div>
      )}
    </div>
  );
}
