/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      // Design tokens — Project Kiwi Design System (UI/UX Polish
      // workstream). `brand` names the same blue already used everywhere
      // as the app's one primary action color, so it has a semantic name
      // instead of every screen hardcoding `blue-600`/`blue-500`. See
      // src/design/tokens.ts for the rest of the semantic color system
      // (success/warning/danger/info/neutral), which intentionally reuses
      // Tailwind's own emerald/blue/amber/red/gray rather than introducing
      // new hex values.
      colors: {
        brand: {
          DEFAULT: "#2563eb", // blue-600
          hover: "#3b82f6", // blue-500
          subtle: "rgb(37 99 235 / 0.2)",
        },
      },
    },
  },
  plugins: [],
};
