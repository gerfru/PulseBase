/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './src/templates/**/*.html',
    './src/static/dashboard.js',
    './src/static/activity.js',
    './src/static/metrics.js',
    './src/static/ml_insights.js',
  ],
  theme: {
    fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] },
    extend: {
      colors: {
        accent: '#10b981',
      },
    },
  },
}
