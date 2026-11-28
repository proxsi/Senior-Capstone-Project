/* Lint configuration for TypeScript and React hooks.
 * Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024. */
import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  // Build output is generated code and must never be linted.
  globalIgnores(['dist']),
  {
    // Lint only TypeScript sources; config and CSS files are handled elsewhere.
    files: ['**/*.{ts,tsx}'],
    /*
     * Layered rule sets, applied in order:
     * - js.configs.recommended: core correctness rules;
     * - tseslint.configs.recommended: TypeScript-aware equivalents;
     * - reactHooks: enforces the Rules of Hooks (stable call order, complete deps);
     * - reactRefresh: keeps modules compatible with Vite's fast-refresh boundary.
     */
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      // Browser globals (window, document, fetch, ...) are used throughout the components.
      globals: globals.browser,
    },
  },
])
