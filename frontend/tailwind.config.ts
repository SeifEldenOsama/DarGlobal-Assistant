import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#12110f",
        paper: "#f7f5f0",
        sand: "#e9e3d8",
        gold: { 400: "#cba565", 500: "#ae8240", 600: "#8c642d" },
      },
      boxShadow: { panel: "0 24px 70px rgba(26, 22, 16, .10)" },
      fontFamily: { sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"], serif: ["Georgia", "serif"] },
    },
  },
  plugins: [],
} satisfies Config;
