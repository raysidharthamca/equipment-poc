/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        status: {
          green: "#16a34a",
          orange: "#ea580c",
          red: "#dc2626",
        },
      },
    },
  },
  plugins: [],
};
