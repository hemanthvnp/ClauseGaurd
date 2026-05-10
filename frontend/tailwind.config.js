/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#0f172a',
        paper: '#f8fafc',
        slateglass: 'rgba(15, 23, 42, 0.7)',
        teal: {
          50: '#ecfeff',
          100: '#cffafe',
          200: '#a5f3fc',
          500: '#06b6d4',
          700: '#0e7490',
        },
        amber: {
          50: '#fffbeb',
          100: '#fef3c7',
          200: '#fde68a',
          500: '#f59e0b',
          700: '#b45309',
        },
      },
      boxShadow: {
        soft: '0 20px 60px rgba(15, 23, 42, 0.18)',
      },
      backgroundImage: {
        'mesh': 'radial-gradient(circle at top left, rgba(6,182,212,0.24), transparent 30%), radial-gradient(circle at top right, rgba(245,158,11,0.2), transparent 32%), linear-gradient(180deg, #0f172a 0%, #111827 40%, #f8fafc 40%, #f8fafc 100%)',
      },
    },
  },
  plugins: [],
};
