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
          sans: ['DM Sans', 'sans-serif'],
          serif: ['Lora', 'Georgia', 'serif'],
        },
        animation: {
          'fade-in': 'fadeIn 0.4s ease forwards',
          'slide-up': 'slideUp 0.4s ease forwards',
        },
        keyframes: {
          fadeIn: {
            '0%': { opacity: '0' },
            '100%': { opacity: '1' },
          },
          slideUp: {
            '0%': { opacity: '0', transform: 'translateY(12px)' },
            '100%': { opacity: '1', transform: 'translateY(0)' },
          },
        },
      },
    },
    plugins: [],
  }