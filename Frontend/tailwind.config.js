/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0A0B0F",
        surface: "#14161E",
        elevated: "#1C1F2B",
        border: "#2A2D3A",
        "text-primary": "#F0F0F5",
        "text-secondary": "#8B8FA3",
        "text-muted": "#4B4F63",
        purple: {
          DEFAULT: "#7C5CFC",
          dim: "#5B3FD4",
          subtle: "rgba(124,92,252,0.12)",
          glow: "rgba(124,92,252,0.25)",
        },
        teal: {
          DEFAULT: "#3AAFB9",
          subtle: "rgba(58,175,185,0.12)",
        },
        underground: "#10B981",
        mainstream: "#6B7280",
        danger: "#EF4444",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      fontSize: {
        "2xs": ["0.65rem", { lineHeight: "1rem" }],
      },
      boxShadow: {
        card: "0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3)",
        "card-hover": "0 8px 32px rgba(0,0,0,0.5), 0 2px 8px rgba(0,0,0,0.3)",
        purple: "0 0 24px rgba(124,92,252,0.2)",
        glow: "0 0 0 1px rgba(124,92,252,0.4), 0 0 20px rgba(124,92,252,0.15)",
      },
      animation: {
        "fade-in": "fadeIn 0.2s ease-out",
        "slide-up": "slideUp 0.3s cubic-bezier(0.16,1,0.3,1)",
        "slide-in-right": "slideInRight 0.35s cubic-bezier(0.16,1,0.3,1)",
        shimmer: "shimmer 1.8s infinite",
      },
      keyframes: {
        fadeIn: { from: { opacity: 0 }, to: { opacity: 1 } },
        slideUp: {
          from: { opacity: 0, transform: "translateY(12px)" },
          to: { opacity: 1, transform: "translateY(0)" },
        },
        slideInRight: {
          from: { opacity: 0, transform: "translateX(40px)" },
          to: { opacity: 1, transform: "translateX(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-400px 0" },
          "100%": { backgroundPosition: "400px 0" },
        },
      },
    },
  },
  plugins: [],
};
