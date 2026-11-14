import { useState } from 'react'
import { Link } from 'react-router-dom'

import { LanguageSwitcher } from '../../components/LanguageSwitcher'
import { Page } from '../../components/Layout'
import { Avatar, ErrorBanner, Field, Icon, PasswordInput } from '../../components/ui'
import { ApiError, api } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { gettext, interpolate } from '../../lib/i18n'
import type { User } from '../../lib/types'
import { NewPasswordFields, requestEmail } from '../auth/AuthPages'

/** Profilo, stato dell'email, password e lingua. */
export function AccountPage() {
  const { user, logout } = useAuth()
  if (!user) return null

  return (
    <Page className="px-5 pt-5 md:px-8 md:pt-8">
      <div className="grid gap-5">
        <Link to="/profilo" className="btn-text btn-sm -mb-3 -ml-3 w-fit">
          <Icon name="arrow_back" size={20} />
          {gettext('Profilo')}
        </Link>
        <header className="flex flex-wrap items-center gap-3">
          <h1 className="flex-1 text-[28px] font-medium leading-9 md:text-headline-small">
            {gettext('Account')}
          </h1>
          <button type="button" className="btn-outlined btn-sm" onClick={() => logout()}>
            <Icon name="logout" size={18} />
            {gettext('Esci')}
          </button>
        </header>

        <ProfileSection user={user} />
        <PublicProfileSection user={user} />
        <EmailSection user={user} />
        <PasswordSection user={user} />
        <LanguageSection />
      </div>
    </Page>
  )
}

function ProfileSection({ user }: { user: User }) {
  const { setUser } = useAuth()
  const [name, setName] = useState(user.display_name)
  const [error, setError] = useState<unknown>(null)
  const [saved, setSaved] = useState(false)

  return (
    <section className="rounded-card bg-surface-container-low p-5">
      <div className="mb-4 flex items-center gap-3">
        <Avatar name={user.display_name} size={44} />
        <div className="min-w-0">
          <h2 className="text-body-large font-medium">{gettext('Nome visibile')}</h2>
          <p className="text-body-small text-on-surface-variant">
            {gettext('Il nome che vedono gli altri.')}
          </p>
        </div>
      </div>
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={async (event) => {
          event.preventDefault()
          setError(null)
          setSaved(false)
          try {
            setUser(await api.patch<User>('/api/me', { display_name: name.trim() }))
            setSaved(true)
          } catch (err) {
            setError(err)
          }
        }}
      >
        <Field label={gettext('Nome')} className="min-w-[220px] flex-1">
          <input
            className="field-input"
            value={name}
            onChange={(event) => {
              setName(event.target.value)
              setSaved(false)
            }}
            required
          />
        </Field>
        <button className="btn-tonal" disabled={!name.trim() || name.trim() === user.display_name}>
          {saved ? gettext('Salvato') : gettext('Salva')}
        </button>
      </form>
      <ErrorBanner error={error} />
    </section>
  )
}

/** Indirizzo del profilo pubblico (ADR 0017): nasce alla prima ricetta pubblica. */
function PublicProfileSection({ user }: { user: User }) {
  const { setUser } = useAuth()
  const [handle, setHandle] = useState(user.handle ?? '')
  const [error, setError] = useState<unknown>(null)
  const [saved, setSaved] = useState(false)
  const clean = handle.trim().toLowerCase()

  return (
    <section className="rounded-card bg-surface-container-low p-5">
      <h2 className="text-body-large font-medium">{gettext('Profilo pubblico')}</h2>
      <p className="mb-4 text-body-small text-on-surface-variant">
        {gettext(
          'Le ricette che rendi pubbliche compaiono in una pagina con il tuo nome visibile, che chiunque può aprire. Senza ricette pubbliche la pagina non esiste.',
        )}
      </p>
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={async (event) => {
          event.preventDefault()
          setError(null)
          setSaved(false)
          try {
            setUser(await api.patch<User>('/api/me', { handle: clean || null }))
            setSaved(true)
          } catch (err) {
            setError(err)
          }
        }}
      >
        <Field label={gettext('Indirizzo')} className="min-w-[220px] flex-1">
          <input
            className="field-input"
            value={handle}
            placeholder={gettext('nasce alla prima ricetta pubblica')}
            onChange={(event) => {
              setHandle(event.target.value)
              setSaved(false)
            }}
          />
        </Field>
        <button className="btn-tonal" disabled={clean === (user.handle ?? '')}>
          {saved ? gettext('Salvato') : gettext('Salva')}
        </button>
      </form>
      {user.handle && (
        <Link to={`/u/${user.handle}`} className="btn-text btn-sm -ml-3 mt-2 w-fit">
          <Icon name="open_in_new" size={18} />
          {`${window.location.host}/u/${user.handle}`}
        </Link>
      )}
      <ErrorBanner error={error} />
    </section>
  )
}

function EmailSection({ user }: { user: User }) {
  const [sent, setSent] = useState(false)
  const verified = Boolean(user.email_verified_at)

  return (
    <section className="rounded-card bg-surface-container-low p-5">
      <h2 className="text-body-large font-medium">{gettext('Email')}</h2>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <span className="min-w-0 flex-1 truncate text-body-large">{user.email}</span>
        <span
          className={
            verified
              ? 'inline-flex items-center gap-1.5 rounded-pill bg-secondary-container px-3 py-1.5 text-body-small font-medium text-on-secondary-container'
              : 'inline-flex items-center gap-1.5 rounded-pill bg-warning-container px-3 py-1.5 text-body-small font-medium text-on-warning-container'
          }
        >
          <Icon name={verified ? 'verified' : 'mark_email_unread'} size={16} />
          {verified ? gettext('Confermata') : gettext('Da confermare')}
        </span>
      </div>
      {!verified && (
        <button
          type="button"
          className="btn-tonal btn-sm mt-3"
          disabled={sent}
          onClick={async () => {
            await requestEmail('verify', user.email).catch(() => undefined)
            setSent(true)
          }}
        >
          <Icon name="forward_to_inbox" size={18} />
          {sent ? gettext('Mail mandata') : gettext('Rimanda la mail di conferma')}
        </button>
      )}
    </section>
  )
}

function PasswordSection({ user }: { user: User }) {
  const [current, setCurrent] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const [changed, setChanged] = useState(false)
  const [linkSent, setLinkSent] = useState(false)
  const fields = error instanceof ApiError ? error.fieldErrors() : {}

  return (
    <section className="rounded-card bg-surface-container-low p-5">
      <h2 className="text-body-large font-medium">{gettext('Password')}</h2>
      <p className="mt-1 text-body-small text-on-surface-variant">
        {gettext(
          'Cambiandola si chiudono le sessioni aperte sugli altri dispositivi; questa resta aperta.',
        )}
      </p>

      {changed && (
        <p className="mt-3 flex items-center gap-2 rounded-row bg-secondary-container px-4 py-3 text-body-medium text-on-secondary-container">
          <Icon name="check_circle" size={20} />
          {gettext('Password cambiata.')}
        </p>
      )}

      <form
        className="mt-4 grid gap-3"
        onSubmit={async (event) => {
          event.preventDefault()
          if (password !== confirm) return
          setBusy(true)
          setError(null)
          setChanged(false)
          try {
            await api.post<void>('/api/auth/password', {
              current_password: current,
              new_password: password,
            })
            setCurrent('')
            setPassword('')
            setConfirm('')
            setChanged(true)
          } catch (err) {
            setError(err)
          } finally {
            setBusy(false)
          }
        }}
      >
        {!fields.current_password && !fields.new_password && <ErrorBanner error={error} />}
        <Field label={gettext('Password attuale')} error={fields.current_password}>
          <PasswordInput
            autoComplete="current-password"
            value={current}
            onChange={setCurrent}
            required
          />
        </Field>
        <NewPasswordFields
          password={password}
          confirm={confirm}
          onPassword={setPassword}
          onConfirm={setConfirm}
          error={fields.new_password}
        />
        <button className="btn-filled" disabled={busy || !current || password !== confirm}>
          {busy ? gettext('Salvo…') : gettext('Cambia password')}
        </button>
      </form>

      <div className="mt-5 border-t border-outline-variant pt-4">
        <p className="text-body-medium">{gettext('Non ricordi quella attuale?')}</p>
        <p className="text-body-small text-on-surface-variant">
          {interpolate(
            gettext('Ti mandiamo a %(email)s un link per reimpostarla, valido 2 ore.'),
            { email: user.email },
            true,
          )}
        </p>
        <button
          type="button"
          className="btn-tonal btn-sm mt-3"
          disabled={linkSent}
          onClick={async () => {
            await requestEmail('reset', user.email).catch(() => undefined)
            setLinkSent(true)
          }}
        >
          <Icon name="lock_reset" size={18} />
          {linkSent
            ? gettext('Link mandato, controlla la mail')
            : gettext('Mandami il link di reset')}
        </button>
      </div>
    </section>
  )
}

/** Lingua dell'interfaccia e delle mail, salvata sul profilo. */
function LanguageSection() {
  return (
    <section className="rounded-card bg-surface-container-low p-5">
      <h2 className="text-body-large font-medium">{gettext('Lingua')}</h2>
      <p className="mt-1 text-body-small text-on-surface-variant">
        {gettext("Vale per l'app e per le mail che ti mandiamo.")}
      </p>
      <LanguageSwitcher className="mt-3" />
    </section>
  )
}
