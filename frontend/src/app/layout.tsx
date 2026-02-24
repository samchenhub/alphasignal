import type { Metadata } from "next";
import "./globals.css";
import { ClerkProvider } from "@clerk/nextjs";
import { AuthNav } from "./components/AuthNav";

export const metadata: Metadata = {
  title: "AlphaSignal — Financial Sentiment Engine",
  description: "Real-time LLM-powered financial news sentiment analysis",
};

const clerkEnabled = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const body = (
    <html lang="en">
      <body className="min-h-screen bg-[#0f1117] text-slate-200">
        {/* Top navbar */}
        <nav className="border-b border-[#2a2d3e] bg-[#0f1117]/95 backdrop-blur sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-6 py-3 flex items-center gap-4">
            {/* Brand */}
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center text-xs font-bold text-white">
                α
              </div>
              <span className="font-semibold text-white tracking-tight text-sm">
                AlphaSignal
              </span>
            </div>

            {/* Live indicator */}
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-green-500/10 border border-green-500/20">
              <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
              <span className="text-xs text-green-400 font-medium">Live</span>
            </div>

            <span className="text-xs text-slate-600 hidden sm:block">
              LLM-powered financial sentiment analysis
            </span>

            <div className="ml-auto flex items-center gap-3">
              <a
                href="https://github.com/samchenhub/alphasignal"
                target="_blank"
                rel="noopener noreferrer"
                className="text-slate-500 hover:text-slate-300 transition-colors text-xs hidden sm:block"
              >
                GitHub
              </a>
              <AuthNav />
            </div>
          </div>
        </nav>

        <main className="max-w-7xl mx-auto px-6 py-6">{children}</main>
      </body>
    </html>
  );

  if (clerkEnabled) {
    return <ClerkProvider>{body}</ClerkProvider>;
  }
  return body;
}
