/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        mist: "#F3F8FB",
        ink: { DEFAULT: "#0F2E44", soft: "#41607A", faint: "#7F98AD" },
        teal: { DEFAULT: "#0B7A83", deep: "#075E66", tint: "#DDF2F2" },
        mint: { DEFAULT: "#2EC4A0", tint: "#E0F7F0" },
        sky: { DEFAULT: "#5AA9F0", tint: "#E5F1FD" },
        coral: { DEFAULT: "#E5484D", tint: "#FDE8E8" },
        amber: { DEFAULT: "#D98714", tint: "#FDF1DE" },
      },
      fontFamily: {
        display: ["Sora", "Segoe UI", "system-ui", "sans-serif"],
        sans: ["Figtree", "Segoe UI", "system-ui", "sans-serif"],
      },
      boxShadow: {
        glass: "0 1px 0 rgba(255,255,255,0.9) inset, 0 18px 40px -22px rgba(15,46,68,0.28)",
        lift: "0 1px 0 rgba(255,255,255,0.9) inset, 0 26px 50px -24px rgba(15,46,68,0.36)",
        clay: "0 10px 18px -10px rgba(11,122,131,0.55), inset 0 -3px 0 rgba(0,0,0,0.12), inset 0 2px 0 rgba(255,255,255,0.35)",
      },
      borderRadius: { xl2: "1.25rem", xl3: "1.75rem" },
    },
  },
  plugins: [],
};
