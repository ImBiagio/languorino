import { Navigate, Route, Routes, useLocation } from 'react-router-dom'

import { AppLayout } from './components/Layout'
import { Skeleton } from './components/ui'
import { AccountPage } from './features/account/AccountPage'
import {
  ForgotPasswordPage,
  LoginPage,
  RegisterPage,
  ResetPasswordPage,
  VerifyEmailPage,
} from './features/auth/AuthPages'
import { HomePage } from './features/home/HomePage'
import { useAuth } from './lib/auth'

function RequireAuth({ children }: { children: JSX.Element }) {
  const { user, ready } = useAuth()
  const location = useLocation()
  if (!ready) return <Skeleton className="m-6 h-24" />
  if (!user) {
    // Dopo il login si torna dove si voleva andare: un link aperto da
    // sloggato non deve finire sulla home.
    const next = location.pathname === '/' ? '' : `?next=${encodeURIComponent(location.pathname)}`
    return <Navigate to={`/accedi${next}`} replace />
  }
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/accedi" element={<LoginPage />} />
      <Route path="/registrati" element={<RegisterPage />} />
      <Route path="/verifica-email/:token" element={<VerifyEmailPage />} />
      <Route path="/password-dimenticata" element={<ForgotPasswordPage />} />
      <Route path="/reset-password/:uid/:token" element={<ResetPasswordPage />} />
      <Route
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route index element={<HomePage />} />
        <Route path="account" element={<AccountPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
