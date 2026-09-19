/** @type {import('tailwindcss').Config} */
// Coverbound warm-literary theme — generated from the redesign prototype.
// Dark mode is class-based (existing app toggles `.dark` on <html> via cookie).
module.exports = {
  content: [
    './app/templates/**/*.html',
    './app/static/js/**/*.js',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        // Warm literary serif for headings; humanist grotesque for body.
        serif: ['Newsreader', 'Georgia', 'serif'],
        sans: ['"Hanken Grotesk"', 'system-ui', 'sans-serif'],
      },
      // Semantic tokens resolve to CSS variables defined in custom.css
      // (:root = light, .dark = dark). Use e.g. bg-surface, text-ink,
      // border-line, text-accent, bg-accent-soft.
      colors: {
        paper:      'var(--paper)',
        surface:    'var(--surface)',
        'surface-2':'var(--surface-2)',
        ink:        'var(--ink)',
        'ink-soft': 'var(--ink-soft)',
        line:       'var(--line)',
        accent:     'var(--accent)',
        'accent-soft':'var(--accent-soft)',
      },
      borderRadius: {
        xl: '14px',
        '2xl': '18px',
        '3xl': '22px',
      },
      boxShadow: {
        card: '0 1px 2px rgba(40,30,20,.04), 0 10px 26px rgba(40,30,20,.05)',
        'card-lift': '0 14px 32px rgba(40,30,20,.12)',
        pop: '0 14px 40px rgba(40,30,20,.22)',
      },
      keyframes: {
        cbxUp: {
          from: { opacity: '0', transform: 'translateY(10px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
        cbxMarquee: {
          from: { transform: 'translateX(0)' },
          to:   { transform: 'translateX(-50%)' },
        },
      },
      animation: {
        up: 'cbxUp .4s ease both',
        marquee: 'cbxMarquee 42s linear infinite',
      },
    },
  },
  plugins: [],
};
