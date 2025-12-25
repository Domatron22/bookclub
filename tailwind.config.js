/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
      "./app/templates/**/*.html",
      "./app/static/js/**/*.js",
    ],
    darkMode: 'class',
    theme: {
      extend: {
        fontFamily: {
          sans: ['Inter', 'sans-serif'],
        },
      },
    },
    plugins: [],
  }