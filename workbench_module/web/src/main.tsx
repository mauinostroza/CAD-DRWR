// Punto de entrada SOLO del arnés (no se copia al workbench).
import { StrictMode, useState } from 'react'
import { createRoot } from 'react-dom/client'
import CadDrwrPage from './cad_drwr/CadDrwrPage'

function App() {
  const [state, setState] = useState<unknown>(undefined)
  return (
    <div style={{ height: '100vh' }}>
      <CadDrwrPage state={state} onState={setState} />
    </div>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
