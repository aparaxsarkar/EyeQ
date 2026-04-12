/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#09111d",
          900: "#102032",
          800: "#16324a",
        },
        sand: "#f4eee4",
        coral: "#ff755c",
        amberglow: "#ffb347",
        citron: "#d9f08c",
        mint: "#7af0bd",
      },
      boxShadow: {
        panel: "0 25px 80px rgba(6, 16, 29, 0.32)",
      },
      backgroundImage: {
        mesh:
          "radial-gradient(circle at top left, rgba(122, 240, 189, 0.18), transparent 30%), radial-gradient(circle at top right, rgba(255, 179, 71, 0.2), transparent 28%), radial-gradient(circle at bottom center, rgba(255, 117, 92, 0.14), transparent 36%)",
      },
      fontFamily: {
        display: ['"Space Grotesk"', '"Avenir Next"', "sans-serif"],
        body: ['"IBM Plex Sans"', '"Helvetica Neue"', "sans-serif"],
      },
    },
  },
  plugins: [],
};

