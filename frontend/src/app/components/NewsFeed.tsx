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

function SentimentScore({ score }: { score: number }) {
  const label = score > 0.3 ? "Bullish" : score < -0.3 ? "Bearish" : "Neutral";
  const color =
    score > 0.3
      ? "text-green-400 bg-green-400/10 border-green-400/20"
      : score < -0.3
        ? "text-red-400 bg-red-400/10 border-red-400/20"
        : "text-slate-400 bg-slate-400/10 border-slate-400/20";
  return (
    <div className={`flex flex-col items-center justify-center px-3 py-2 rounded-lg border ${color} min-w-[60px]`}>
      <span className="text-xs font-medium">{label}</span>
      <span className="text-sm font-bold font-mono">
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
          <div key={i} className="h-28 bg-[#1a1d2e] rounded-xl animate-pulse border border-[#2a2d3e]" />
        ))}
      </div>
    );
  }

  if (error || !data || data.length === 0) {
    return (
      <div className="text-center py-20 text-slate-500 bg-[#1a1d2e] rounded-xl border border-[#2a2d3e]">
        <p className="text-4xl mb-3">📰</p>
        <p className="font-medium text-slate-400">No analyzed articles for {ticker} yet</p>
        <p className="text-xs mt-1 text-slate-600">Ingestion runs every 15 minutes — check back soon</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-slate-500 mb-3">{data.length} analyzed articles · last 7 days</p>
      {data.map((item) => {
        const score = item.sentiment_score;
        const accentColor =
          score !== null && score > 0.3
            ? "bg-green-500"
            : score !== null && score < -0.3
              ? "bg-red-500"
              : "bg-slate-600";

        return (
          <article
            key={item.article_id}
            className="bg-[#1a1d2e] border border-[#2a2d3e] rounded-xl overflow-hidden hover:border-slate-600 transition-all hover:shadow-lg hover:shadow-black/20 group"
          >
            <div className="flex">
              {/* Left accent bar */}
              <div className={`w-1 shrink-0 ${accentColor}`} />

              <div className="flex-1 flex items-start gap-4 p-4">
                {/* Main content */}
                <div className="flex-1 min-w-0">
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm font-medium text-slate-200 hover:text-white line-clamp-2 leading-snug group-hover:text-white transition-colors"
                  >
                    {item.title}
                  </a>

                  {item.summary && (
                    <p className="text-xs text-slate-500 mt-1.5 line-clamp-2 leading-relaxed">
                      {item.summary}
                    </p>
                  )}

                  <div className="flex flex-wrap items-center gap-2 mt-2.5">
                    {/* Key event tags */}
                    {item.key_events?.slice(0, 2).map((evt, i) => (
                      <span
                        key={i}
                        className="text-xs px-2 py-0.5 rounded-md bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-mono"
                      >
                        {evt.type.replace(/_/g, " ")}
                      </span>
                    ))}

                    <span className="text-xs text-slate-600">{item.source}</span>

                    {item.published_at && (
                      <span className="text-xs text-slate-600">
                        {new Date(item.published_at).toLocaleDateString("en-US", {
                          month: "short", day: "numeric"
                        })}
                      </span>
                    )}

                    {item.confidence !== null && (
                      <span className="text-xs text-slate-600">
                        {(item.confidence * 100).toFixed(0)}% conf.
                      </span>
                    )}
                  </div>
                </div>

                {/* Sentiment score badge */}
                {score !== null && <SentimentScore score={score} />}
              </div>
            </div>
          </article>
        );
      })}
    </div>
  );
}
