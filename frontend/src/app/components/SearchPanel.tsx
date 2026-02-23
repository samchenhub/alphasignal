"use client";

import { useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface SearchResult {
  article_id: string;
  ticker: string;
  market: string;
  title: string;
  url: string;
  summary: string | null;
  sentiment_score: number | null;
  published_at: string | null;
  similarity: number | null;
}

interface Props {
  market: "US" | "CN";
}

export function SearchPanel({ market }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  async function handleSearch() {
    if (!query.trim()) return;
    setIsLoading(true);
    setSearched(true);
    try {
      const res = await fetch(`${API}/api/v1/search/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, market, days: 90, limit: 10 }),
      });
      const data = await res.json();
      setResults(Array.isArray(data) ? data : []);
    } catch {
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <p className="text-sm text-slate-400 mb-3">
          Search analyzed articles by topic, event type, or company name.
          Uses PostgreSQL full-text search (pgvector semantic search when embeddings are populated).
        </p>
        <div className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder={
              market === "US"
                ? 'e.g. "supply chain disruption" or "earnings miss"'
                : 'e.g. "供应链危机" 或 "业绩预警"'
            }
            className="flex-1 bg-[#1a1d2e] border border-[#2a2d3e] rounded-lg px-4 py-2.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-indigo-500 transition-colors"
          />
          <button
            onClick={handleSearch}
            disabled={isLoading}
            className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 rounded-lg text-sm font-medium text-white transition-colors"
          >
            {isLoading ? "Searching..." : "Search"}
          </button>
        </div>
      </div>

      {searched && results.length === 0 && !isLoading && (
        <div className="text-center py-12 text-slate-500">
          <p>No results found for "{query}"</p>
        </div>
      )}

      {results.length > 0 && (
        <div className="space-y-3">
          {results.map((r) => (
            <div
              key={r.article_id}
              className="bg-[#1a1d2e] border border-[#2a2d3e] rounded-xl p-4"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <a
                    href={r.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm font-medium text-slate-200 hover:text-white"
                  >
                    {r.title}
                  </a>
                  {r.summary && (
                    <p className="text-xs text-slate-400 mt-1">{r.summary}</p>
                  )}
                  <div className="flex gap-3 mt-2">
                    <span className="text-xs font-mono text-indigo-400">
                      {r.ticker}
                    </span>
                    <span className="text-xs text-slate-600">{r.market}</span>
                    {r.published_at && (
                      <span className="text-xs text-slate-600">
                        {new Date(r.published_at).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                </div>
                {r.sentiment_score !== null && (
                  <span
                    className={`text-xs font-mono shrink-0 ${
                      r.sentiment_score > 0
                        ? "text-green-400"
                        : r.sentiment_score < 0
                          ? "text-red-400"
                          : "text-gray-400"
                    }`}
                  >
                    {r.sentiment_score > 0 ? "+" : ""}
                    {r.sentiment_score.toFixed(2)}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
