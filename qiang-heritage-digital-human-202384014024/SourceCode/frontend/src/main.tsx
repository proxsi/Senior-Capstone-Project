/* Mount the React application and global styles.
 * Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024. */
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'

/*
 * Application entry point.
 * `index.html` ships a single <div id="root"> mount node; the non-null assertion is safe
 * because Vite injects the module after the DOM skeleton is parsed.
 *
 * StrictMode is a development-only wrapper: it intentionally mounts, unmounts, and remounts
 * every component once, and runs effects twice, to surface missing effect cleanup (stale
 * audio listeners, dangling intervals) early. It has no effect on the production build.
 */
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
