import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ops: {
          bg: "#020617",        // slate-950
          surface: "#0f172a",   // slate-900
          border: "#1e293b",    // slate-800
          muted: "#64748b",     // slate-500
          text: "#f1f5f9",      // slate-100
          green: "#10b981",     // emerald-500
          red: "#ef4444",       // red-500
          amber: "#f59e0b",     // amber-500
          blue: "#3b82f6",      // blue-500
        },
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
