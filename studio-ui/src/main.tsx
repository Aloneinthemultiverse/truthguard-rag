import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import App from './App'
import About from './About'
const isAbout = window.location.pathname.replace(/\/$/, '') === '/about'
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>{isAbout ? <About/> : <App/>}</React.StrictMode>)
