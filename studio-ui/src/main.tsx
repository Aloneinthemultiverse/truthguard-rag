import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import App from './App'
import About from './About'
import Architecture from './Architecture'
const p = window.location.pathname.replace(/\/$/, '')
const Page = p === '/about' ? About : p === '/architecture' ? Architecture : App
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><Page/></React.StrictMode>)
