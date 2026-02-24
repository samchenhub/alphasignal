/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    // API_URL is a server-only env var — never exposed to the browser.
    // Vercel forwards all /api/* requests to the Railway backend.
    const backendUrl = process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
