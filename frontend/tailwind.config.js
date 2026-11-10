/** @type {import('tailwindcss').Config} */
// Palette tonale Material 3 generata dal seed #a8433f. I valori veri stanno come
// custom properties in src/index.css: qui si mappano solo sui nomi di ruolo M3,
// così nel markup si scrive `bg-surface-container` e non un hex.
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: 'var(--primary)',
        'on-primary': 'var(--on-primary)',
        'primary-container': 'var(--primary-container)',
        'on-primary-container': 'var(--on-primary-container)',
        secondary: 'var(--secondary)',
        'secondary-container': 'var(--secondary-container)',
        'on-secondary-container': 'var(--on-secondary-container)',
        tertiary: 'var(--tertiary)',
        'tertiary-container': 'var(--tertiary-container)',
        'on-tertiary-container': 'var(--on-tertiary-container)',
        warning: 'var(--warning)',
        'warning-container': 'var(--warning-container)',
        'on-warning-container': 'var(--on-warning-container)',
        error: 'var(--error)',
        'error-container': 'var(--error-container)',
        'on-error-container': 'var(--on-error-container)',
        success: 'var(--success)',
        'success-container': 'var(--success-container)',
        'on-success-container': 'var(--on-success-container)',
        surface: 'var(--surface)',
        'surface-container-low': 'var(--surface-container-low)',
        'surface-container': 'var(--surface-container)',
        'surface-container-high': 'var(--surface-container-high)',
        'surface-container-highest': 'var(--surface-container-highest)',
        'on-surface': 'var(--on-surface)',
        'on-surface-variant': 'var(--on-surface-variant)',
        outline: 'var(--outline)',
        'outline-variant': 'var(--outline-variant)',
      },
      borderRadius: {
        panel: '28px',
        card: '24px',
        row: '20px',
        nested: '18px',
        nav: '16px',
        fab: '22px',
        pill: '999px',
      },
      fontFamily: {
        sans: ['"Roboto Flex"', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"Roboto Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      fontSize: {
        // Scala del design: [size, {lineHeight, letterSpacing, fontWeight}]
        'display-large': ['60px', { lineHeight: '64px', letterSpacing: '-1px', fontWeight: '600' }],
        'display-medium': ['56px', { lineHeight: '60px', fontWeight: '600' }],
        'display-small': ['46px', { lineHeight: '52px', letterSpacing: '-0.5px', fontWeight: '600' }],
        'headline-medium': ['40px', { lineHeight: '46px', fontWeight: '600' }],
        'headline-small': ['32px', { lineHeight: '38px', letterSpacing: '-0.2px', fontWeight: '500' }],
        'title-large': ['26px', { lineHeight: '32px', fontWeight: '600' }],
        'title-medium': ['20px', { lineHeight: '28px', fontWeight: '600' }],
        'body-large': ['16px', { lineHeight: '24px' }],
        'body-medium': ['14px', { lineHeight: '20px' }],
        'body-small': ['13px', { lineHeight: '18px' }],
        'label-small': ['12px', { lineHeight: '16px', fontWeight: '500' }],
        'amount-row': ['19px', { fontWeight: '600' }],
      },
      boxShadow: {
        fab: '0 1px 3px rgba(0,0,0,0.12)',
        'fab-mobile': '0 4px 12px rgba(0,0,0,0.2)',
        sheet: '0 8px 24px rgba(0,0,0,0.18)',
      },
      transitionTimingFunction: {
        // "emphasized decelerate" M3
        m3: 'cubic-bezier(0.2, 0, 0, 1)',
      },
    },
  },
  plugins: [],
}
