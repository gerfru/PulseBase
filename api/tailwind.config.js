/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './src/templates/**/*.html',
    // Alle Frontend-JS scannen — viele Dateien (epilepsy.js, help.js,
    // dashboard-hero.js, metrics-ml.js …) rendern Tailwind-Klassen dynamisch.
    // Eine selektive Liste ließ JS-only-Klassen (z. B. text-violet-700)
    // unkompiliert und damit wirkungslos.
    './src/static/**/*.js',
  ],
  theme: {
    fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] },
    // accent lebt als CSS-Token --accent in static/style.css (Single Source of Truth);
    // die Tailwind-accent-Utility wurde nie genutzt.
  },
}
