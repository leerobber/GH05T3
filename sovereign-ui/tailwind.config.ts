import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ghost: {
          bg:       "#050505",
          panel:    "#0F0F11",
          hover:    "#141417",
          input:    "#0A0A0C",
          amber:    "#F59E0B",
          crimson:  "#E11D48",
          success:  "#10B981",
          silver:   "#E5E7EB",
        },
      },
      fontFamily: {
        serif: ["var(--font-serif)", "Georgia", "serif"],
        mono:  ["var(--font-mono)", "Fira Code", "monospace"],
        sans:  ["var(--font-sans)", "system-ui", "sans-serif"],
      },
      animation: {
        "pulse-amber": "pulse-amber 2s ease-in-out infinite",
        scanline:      "scanline 8s linear infinite",
      },
      keyframes: {
        "pulse-amber": {
          "0%, 100%": { opacity: "0.6" },
          "50%":       { opacity: "1" },
        },
        scanline: {
          "0%":   { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100vh)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
