import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

// StrictMode ejecuta los efectos dos veces en desarrollo (solo dev): los useEffect con fetch deben tolerar peticiones duplicadas.
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
