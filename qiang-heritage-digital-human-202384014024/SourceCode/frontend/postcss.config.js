/* PostCSS configuration for Tailwind and vendor prefixes.
 * Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024. */
/*
 * PostCSS pipeline, applied to every imported CSS file.
 * `tailwindcss` expands the @tailwind directives in src/index.css against the content globs
 * in tailwind.config.js, and `autoprefixer` adds the vendor prefixes required by older
 * browsers. Order matters: Tailwind must run before autoprefixer sees the generated rules.
 */
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}