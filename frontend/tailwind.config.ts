import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        bull: "#22c55e",    // green for positive sentiment
        bear: "#ef4444",    // red for negative sentiment
        neutral: "#6b7280", // gray for neutral
      },
    },
  },
  plugins: [],
} satisfies Config;
