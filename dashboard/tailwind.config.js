/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/js/**/*.js",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        discord: {
          dark: '#36393f',
          darker: '#2f3136',
          darkest: '#202225',
          blurple: '#5865f2',
          green: '#3ba55c',
          yellow: '#faa61a',
          red: '#ed4245',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
