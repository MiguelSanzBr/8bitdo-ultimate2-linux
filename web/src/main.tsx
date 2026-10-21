import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './adapters/ui/App'
import { browserWiring } from './adapters/ui/wiring'

createRoot(document.getElementById('root') as HTMLElement).render(
  <StrictMode>
    <App wiring={browserWiring()} />
  </StrictMode>,
)
