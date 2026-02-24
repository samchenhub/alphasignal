"use client";

import useSWR from "swr";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

interface NewsItem {
  article_id: string;
  ticker: string;
  market: string;
  source: string;
  title: string;
  url: string;
  published_at: string | null;
  sentiment_score: number | null;
  confidence: number | null;
  summary: string | null;
  key_events: Array<{ type: string; description: string }> | null;
}

function SentimentBar({ score }: { score: number }) {
  const pct = ((score + 1) / 2) * 100; // map -1..1 to 0..100%
  const color =
    score > 0.3 ? "bg-green-500" : score < -0.3 ? "bg-red-500" : "bg-gray-500";
  return (
    <div className="flex items-center gap-2 mt-1">
      <div className="w-24 h-1.5 bg-[#2a2d3e] rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span
        className={`text-xs font-mono ${
          score > 0.3
            ? "text-green-400"
            : score < -0.3
              ? "text-red-400"
              : "text-gray-400"
        }`}
      >
        {score > 0 ? "+" : ""}
        {score.toFixed(2)}
      </span>
    </div>
  );
}

interface Props {
  ticker: string;
  market: "US" | "CN";
}

export function NewsFeed({ ticker, market }: Props) {
  const { data, error, isLoading } = useSWR<NewsItem[]>(
    `/api/v1/news/${ticker}?days=7&limit=30`,
    fetcher,
    { refreshInterval: 60_000 }
  );

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-24 bg-[#1a1d2e] rounded-xl animate-pulse" />
        ))}
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="text-center py-16 text-slate-500">
        <p className="text-3xl mb-3">📰</p>
        <p>No analyzed articles for {ticker} yet</p>
        <p className="text-xs mt-1">Ingestion runs every 15 minutes</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {data.map((item) => (
        <article
          key={item.article_id}
          className="bg-[#1a1d2e] border border-[#2a2d3e] rounded-xl p-4 hover:border-slate-600 transition-colors"
        >
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm font-medium text-slate-200 hover:text-white line-clamp-2 leading-snug"
              >
                {item.title}
              </a>

              {item.summary && (
                <p className="text-xs text-slate-400 mt-1.5 line-clamp-2">
                  {item.summary}
                </p>
              )}

              {item.key_events && item.key_events.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {item.key_events.slice(0, 2).map((evt, i) => (
                    <span
                      key={i}
                      className="text-xs px-2 py-0.5 rounded bg-[#2a2d3e] text-slate-400 font-mono"
                    >
                      {evt.type}
                    </span>
                  ))}
                </div>
              )}

              <div className="flex items-center gap-3 mt-2">
                <span className="text-xs text-slate-600">{item.source}</span>
                {item.published_at && (
                  <span className="text-xs text-slate-600">
                    {new Date(item.published_at).toLocaleDateString()}
                  </span>
                )}
                {item.confidence !== null && (
                  <span className="text-xs text-slate-600">
                    {(item.confidence * 100).toFixed(0)}% confidence
                  </span>
                )}
              </div>
            </div>

            {item.sentiment_score !== null && (
              <div className="shrink-0 text-right">
                <SentimentBar score={item.sentiment_score} />
              </div>
            )}
          </div>
        </article>
      ))}
    </div>
  );
}
