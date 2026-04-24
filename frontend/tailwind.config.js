/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#18230f",
        moss: "#2f4f28",
        sand: "#f3efe3",
        clay: "#d9c7a2",
        rose: "#d46a6a",
      },
      boxShadow: {
        soft: "0 20px 45px rgba(24, 35, 15, 0.12)",
      },
      fontFamily: {
        display: ['"DM Serif Display"', "serif"],
        body: ['"Manrope"', "sans-serif"],
      },
    },
  },
  plugins: [],
};
