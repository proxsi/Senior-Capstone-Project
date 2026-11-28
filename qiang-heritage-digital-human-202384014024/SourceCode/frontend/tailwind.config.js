/* Tailwind content discovery and theme configuration.
 * Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024. */
/** @type {import('tailwindcss').Config} */
export default {
  /*
   * Content globs tell Tailwind which files to scan for class names. Anything outside these
   * paths can still work at runtime but its utilities will be purged from the production CSS,
   * so new component directories must be added here. `index.html` is included because the
   * root document also carries class names.
   */
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      /*
       * Project palette. The `qiang*` tokens are semantic aliases used throughout the JSX
       * (qiangRed for headers/CTAs, qiangDark for the page background, and so on), which keeps
       * the ethnic visual identity in one place instead of hard-coded hex values.
       */
      colors: {
        qiangRed: '#D72638',
        qiangDark: '#1A1A1A',
        qiangWhite: '#FFFFFF',
        qiangBlue: '#3B82F6',
        qiangYellow: '#F59E0B',
        qiangPurple: '#8B5CF6',
        qiangGray: '#F3F4F6',
      },
      /* Inter first, then platform UI fonts as a graceful fallback. */
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}