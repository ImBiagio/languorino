// Errori del frontend a GlitchTip (protocollo Sentry), come il backend.
// Parte solo se la build ha VITE_SENTRY_DSN (variabile del repo su GitHub,
// passata alla build dell'immagine web). Niente dati personali, niente
// tracce delle prestazioni ne' registrazioni della sessione.
import * as Sentry from '@sentry/react'

export function initSentry() {
  const dsn = import.meta.env.VITE_SENTRY_DSN as string | undefined
  if (!dsn) return
  Sentry.init({
    dsn,
    environment: import.meta.env.MODE,
    sendDefaultPii: false,
    tracesSampleRate: 0,
    integrations: [],
  })
}
