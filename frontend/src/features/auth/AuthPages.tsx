import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { LanguageSwitcher } from '../../components/LanguageSwitcher'
import { ErrorBanner, Field, Icon, PasswordInput, Skeleton } from '../../components/ui'
import { ApiError, api } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { gettext } from '../../lib/i18n'

/**
 * Pagina piena: una card su superficie neutra con in testa una fascia colorata
 * e il marchio. Il colore primario resta un accento, non tutto lo sfondo.
 */
function Shell({
  title,
  children,
  footer,
}: {
  title: string
  children: ReactNode
  footer?: ReactNode
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-container-low p-4 sm:p-6">
      <div className="w-full max-w-md">
        <div className="card-elevated overflow-hidden bg-surface">
          <div className="relative h-24">
            <div className="h-full w-full bg-primary-container" />
            <img
              src="/logo-mark.svg"
              alt=""
              width={64}
              height={64}
              className="absolute -bottom-8 left-6 h-16 w-16 rounded-[18px] shadow-fab-mobile sm:left-8"
            />
          </div>
          <div className="px-6 pb-6 pt-11 sm:px-8 sm:pb-8">
            <p className="text-title-large">Languorino</p>
            <p className="text-body-medium text-on-surface-variant">
              {gettext('Il tagline della tua app.')}
            </p>
            <h1 className="mb-4 mt-6 text-title-medium">{title}</h1>
            {children}
          </div>
        </div>

        {footer && <div className="mt-4 text-center text-body-medium">{footer}</div>}
        <div className="mt-4 flex justify-center">
          <LanguageSwitcher />
        </div>
      </div>
    </div>
  )
}

/** Il login risponde con questo codice se l'email non e' ancora confermata. */
function isUnverified(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    (error.data as { code?: string } | null)?.code === 'email_not_verified'
  )
}

/** Le due mail "a richiesta": rispondono sempre 204, non dicono chi e' registrato. */
export function requestEmail(kind: 'verify' | 'reset', email: string) {
  const path = kind === 'verify' ? '/api/auth/verify-email/resend' : '/api/auth/password-reset'
  return api.post<void>(path, { email })
}

function ResendVerification({ email }: { email: string }) {
  const [state, setState] = useState<'idle' | 'busy' | 'sent'>('idle')
  return (
    <div className="rounded-row bg-surface-container p-4 text-body-medium">
      <p>{gettext("Prima di entrare conferma l'indirizzo dal link che ti abbiamo mandato.")}</p>
      <button
        type="button"
        className="btn-tonal btn-sm mt-3"
        disabled={state !== 'idle'}
        onClick={async () => {
          setState('busy')
          await requestEmail('verify', email).catch(() => undefined)
          setState('sent')
        }}
      >
        <Icon name="forward_to_inbox" size={18} />
        {state === 'sent' ? gettext('Mail rimandata') : gettext('Rimanda la mail')}
      </button>
    </div>
  )
}

/**
 * Dove andare dopo login o registrazione (`?next=/unisciti/...`): solo
 * percorsi interni, cosi' un link falso non manda fuori dall'app.
 */
function useNextPath(): { next: string; query: string } {
  const [params] = useSearchParams()
  const raw = params.get('next') ?? ''
  const next = raw.startsWith('/') && !raw.startsWith('//') ? raw : '/'
  return { next, query: next === '/' ? '' : `?next=${encodeURIComponent(next)}` }
}

export function LoginPage() {
  const { login, user } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const { next, query } = useNextPath()

  if (user) return <Navigate to={next} replace />

  return (
    <Shell
      title={gettext('Accedi')}
      footer={
        <span className="text-on-surface-variant">
          {gettext('Non hai un account?')}{' '}
          <Link
            className="font-medium text-primary underline-offset-2 hover:underline"
            to={`/registrati${query}`}
          >
            {gettext('Registrati')}
          </Link>
        </span>
      }
    >
      <form
        className="grid gap-3"
        onSubmit={async (event) => {
          event.preventDefault()
          setBusy(true)
          setError(null)
          try {
            await login(email, password)
          } catch (err) {
            setError(err)
          } finally {
            setBusy(false)
          }
        }}
      >
        {isUnverified(error) ? <ResendVerification email={email} /> : <ErrorBanner error={error} />}
        <Field label={gettext('Email')}>
          <input
            className="field-input"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </Field>
        <Field label={gettext('Password')}>
          <PasswordInput
            autoComplete="current-password"
            value={password}
            onChange={setPassword}
            required
          />
        </Field>
        <button className="btn-filled mt-1 w-full" disabled={busy}>
          {busy ? gettext('Accesso…') : gettext('Entra')}
        </button>
        <Link
          to={
            email
              ? `/password-dimenticata?email=${encodeURIComponent(email)}`
              : '/password-dimenticata'
          }
          className="btn-text w-full"
        >
          {gettext('Password dimenticata?')}
        </Link>
      </form>
    </Shell>
  )
}

export function RegisterPage() {
  const { register, user } = useAuth()
  const [email, setEmail] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const { next, query } = useNextPath()

  if (user) return <Navigate to={next} replace />

  return (
    <Shell
      title={gettext('Crea un account')}
      footer={
        <span className="text-on-surface-variant">
          {gettext('Hai già un account?')}{' '}
          <Link
            className="font-medium text-primary underline-offset-2 hover:underline"
            to={`/accedi${query}`}
          >
            {gettext('Accedi')}
          </Link>
        </span>
      }
    >
      {message ? (
        <div className="grid gap-3">
          <p className="text-body-medium">{message}</p>
          <Link className="btn-tonal w-full" to={`/accedi${query}`}>
            {gettext('Torna al login')}
          </Link>
        </div>
      ) : (
        <form
          className="grid gap-3"
          onSubmit={async (event) => {
            event.preventDefault()
            setBusy(true)
            setError(null)
            try {
              setMessage(await register(email, password, displayName))
            } catch (err) {
              setError(err)
            } finally {
              setBusy(false)
            }
          }}
        >
          <ErrorBanner error={error} />
          <Field label={gettext('Nome')}>
            <input
              className="field-input"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder={gettext('Come ti chiamano')}
            />
          </Field>
          <Field label={gettext('Email')}>
            <input
              className="field-input"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </Field>
          <Field
            label={gettext('Password')}
            error={error instanceof ApiError ? error.fieldErrors().password : undefined}
            hint={gettext('Almeno 10 caratteri.')}
          >
            <PasswordInput
              autoComplete="new-password"
              value={password}
              onChange={setPassword}
              required
            />
          </Field>
          <button className="btn-filled mt-1 w-full" disabled={busy}>
            {busy ? gettext('Creazione…') : gettext('Crea account')}
          </button>
        </form>
      )}
    </Shell>
  )
}

export function VerifyEmailPage() {
  const { token } = useParams()
  const { verifyEmail } = useAuth()
  const [error, setError] = useState<unknown>(null)
  const [done, setDone] = useState(false)

  useEffect(() => {
    if (!token) return
    verifyEmail(token)
      .then(() => setDone(true))
      .catch(setError)
  }, [token, verifyEmail])

  if (done) return <Navigate to="/" replace />
  return (
    <Shell title={gettext('Conferma email')}>
      {error ? <ErrorBanner error={error} /> : <Skeleton className="h-12" />}
    </Shell>
  )
}

export function ForgotPasswordPage() {
  const [params] = useSearchParams()
  const [email, setEmail] = useState(params.get('email') ?? '')
  const [error, setError] = useState<unknown>(null)
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)

  return (
    <Shell
      title={gettext('Password dimenticata')}
      footer={
        <Link className="font-medium text-primary underline-offset-2 hover:underline" to="/accedi">
          {gettext('Torna al login')}
        </Link>
      }
    >
      {sent ? (
        <p className="text-body-medium">
          {gettext('Se')} <strong>{email}</strong>{' '}
          {gettext(
            'ha un account, tra poco ti arriva una mail con il link per scegliere una nuova password. Il link vale 2 ore. Controlla anche lo spam.',
          )}
        </p>
      ) : (
        <form
          className="grid gap-3"
          onSubmit={async (event) => {
            event.preventDefault()
            setBusy(true)
            setError(null)
            try {
              await requestEmail('reset', email)
              setSent(true)
            } catch (err) {
              setError(err)
            } finally {
              setBusy(false)
            }
          }}
        >
          <p className="text-body-medium text-on-surface-variant">
            {gettext("Scrivi l'email dell'account: ti mandiamo un link per sceglierne una nuova.")}
          </p>
          <ErrorBanner error={error} />
          <Field label={gettext('Email')}>
            <input
              className="field-input"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              autoFocus
            />
          </Field>
          <button className="btn-filled mt-1 w-full" disabled={busy}>
            {busy ? gettext('Invio…') : gettext('Mandami il link')}
          </button>
        </form>
      )}
    </Shell>
  )
}

/** Nuova password due volte, con lo stesso controllo locale in login e in Account. */
export function NewPasswordFields({
  password,
  confirm,
  onPassword,
  onConfirm,
  error,
}: {
  password: string
  confirm: string
  onPassword: (value: string) => void
  onConfirm: (value: string) => void
  error?: string
}) {
  const mismatch = confirm.length > 0 && confirm !== password
  return (
    <>
      <Field label={gettext('Nuova password')} error={error} hint={gettext('Almeno 10 caratteri.')}>
        <PasswordInput
          autoComplete="new-password"
          value={password}
          onChange={onPassword}
          required
        />
      </Field>
      <Field
        label={gettext('Ripeti la nuova password')}
        error={mismatch ? gettext('Non coincide.') : undefined}
      >
        <PasswordInput autoComplete="new-password" value={confirm} onChange={onConfirm} required />
      </Field>
    </>
  )
}

export function ResetPasswordPage() {
  const { uid, token } = useParams()
  const { resetPassword } = useAuth()
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  return (
    <Shell title={gettext('Nuova password')}>
      <form
        className="grid gap-3"
        onSubmit={async (event) => {
          event.preventDefault()
          if (password !== confirm) return
          setBusy(true)
          setError(null)
          try {
            await resetPassword(uid ?? '', token ?? '', password)
            navigate('/', { replace: true })
          } catch (err) {
            setError(err)
          } finally {
            setBusy(false)
          }
        }}
      >
        <ErrorBanner error={error} />
        <NewPasswordFields
          password={password}
          confirm={confirm}
          onPassword={setPassword}
          onConfirm={setConfirm}
          error={error instanceof ApiError ? error.fieldErrors().new_password : undefined}
        />
        <button className="btn-filled mt-1 w-full" disabled={busy || password !== confirm}>
          {busy ? gettext('Salvo…') : gettext('Salva ed entra')}
        </button>
        <Link to="/password-dimenticata" className="btn-text w-full">
          {gettext('Il link non va? Chiedine uno nuovo')}
        </Link>
      </form>
    </Shell>
  )
}
