import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import App from './App'
import About from './About'
import Architecture from './Architecture'
const p = window.location.pathname.replace(/\/$/, '')
// Studio talks to the local Python backend, so it is only the landing page on localhost.
// On a deployed host, "/" serves the product page instead.
const local = /^(localhost|127\.0\.0\.1)$/.test(window.location.hostname)
const Page = p === '/about' ? About
  : p === '/architecture' ? Architecture
  : p === '/studio' ? App
  : local ? App : About
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><Page/></React.StrictMode>)
