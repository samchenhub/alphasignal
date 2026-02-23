import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AlphaSignal — Financial Sentiment Engine",
  description: "Real-time LLM-powered financial news sentiment analysis",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[#0f1117] text-slate-200">
        <nav className="border-b border-[#2a2d3e] px-6 py-4 flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          <span className="font-semibold text-white tracking-tight">AlphaSignal</span>
          <span className="text-xs text-slate-500 ml-1">
            LLM-powered financial sentiment
          </span>
        </nav>
        <main className="max-w-7xl mx-auto px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
