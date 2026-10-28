/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#FEF3F2",
          100: "#FDE5E4",
          200: "#FBCCC9",
          300: "#F7A69F",
          400: "#F0786C",
          500: "#E4503F",
          600: "#C81E1E",
          700: "#A51818",
          800: "#851A1A",
          900: "#6F1C1C",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
      },
      boxShadow: {
        card: "0 1px 2px rgba(16, 24, 40, 0.06), 0 1px 3px rgba(16, 24, 40, 0.08)",
      },
    },
  },
  plugins: [],
};
