/**
 * Design tokens sampled directly from the reference screens in UI_SCREENS/.
 * The reference canvas is 1440 x 906 CSS px, exported at 3x.
 */
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          DEFAULT: '#143A7A', // primary actions, logo, links
          hover: '#12326A',
          soft: '#E8EEF8', // chips, active pills
          border: '#C6D0DF',
        },
        ink: {
          DEFAULT: '#14202E', // headings, dark surfaces, dark buttons
          muted: '#475569',
          subtle: '#64748B',
        },
        page: '#F4F5F7',
        line: '#DDE3EA',
        viewer: {
          bg: '#2B3440',
          footer: '#1E262F',
        },
        ok: {
          DEFAULT: '#16794C',
          bg: '#E6F4EC',
        },
        warn: {
          DEFAULT: '#B45309',
          bg: '#FEF3E2',
        },
        bad: {
          DEFAULT: '#B42318',
          bg: '#FDECEA',
          tint: '#FEF7F7',
        },
        highlight: {
          DEFAULT: '#F1E8C9',
          border: '#C9A227',
        },
        manual: '#FFFAF3',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
      },
      fontSize: {
        '2xs': ['11px', '15px'],
        xs: ['12px', '16px'],
        sm: ['13px', '18px'],
        base: ['14px', '20px'],
        md: ['15px', '22px'],
        lg: ['17px', '24px'],
        xl: ['20px', '28px'],
        '2xl': ['24px', '31px'],
        '3xl': ['32px', '38px'],
      },
      borderRadius: {
        card: '12px',
        control: '10px',
        pill: '999px',
      },
      boxShadow: {
        card: '0 1px 2px rgba(16, 24, 40, 0.04)',
        pop: '0 8px 24px rgba(16, 24, 40, 0.12)',
        viewerpage: '0 6px 24px rgba(0, 0, 0, 0.35)',
      },
      spacing: {
        header: '68px',
        subbar: '41px',
        rail: '75px',
      },
    },
  },
  plugins: [],
}
