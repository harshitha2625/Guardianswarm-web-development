export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "SFMono-Regular", "Menlo", "monospace"]
      },
      colors: {
        bunker: "#07090f",
        panel: "#101722",
        line: "#223043",
        signal: "#19f0b6",
        amber: "#f8b84e",
        danger: "#ff5c7c"
      },
      boxShadow: {
        glow: "0 0 34px rgba(25, 240, 182, 0.18)"
      }
    }
  },
  plugins: []
};
