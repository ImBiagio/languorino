import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import './index.css'
import { loadCatalog } from './lib/i18n'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
})

// Prima il catalogo delle traduzioni, poi l'app: le etichette definite come
// costanti di modulo chiamano gettext() quando il modulo viene importato.
async function start() {
  await loadCatalog()
  const [{ default: App }, { AuthProvider }, { ConfirmProvider }] = await Promise.all([
    import('./App'),
    import('./lib/auth'),
    import('./components/ConfirmDialog'),
  ])
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AuthProvider>
            <ConfirmProvider>
              <App />
            </ConfirmProvider>
          </AuthProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </React.StrictMode>,
  )
}

void start()
