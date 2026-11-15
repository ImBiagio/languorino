import { useState } from 'react'
import { Link } from 'react-router-dom'

import { LanguageSwitcher } from '../../components/LanguageSwitcher'
import { Page } from '../../components/Layout'
import { useAuthConfig } from '../../api/hooks'
import { Avatar, ErrorBanner, Field, Icon } from '../../components/ui'
import { api } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { gettext } from '../../lib/i18n'
import type { User } from '../../lib/types'

/** Account nell'app: indirizzo pubblico e lingua; il resto sta su cornhub. */
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

        <SuiteAccountSection user={user} />
        <PublicProfileSection user={user} />
        <LanguageSection />
      </div>
    </Page>
  )
}

/**
 * Nome, email e password sono dell'account della suite e si cambiano su
 * cornhub (ADR 0021): qui si vedono soltanto, con i link per cambiarli.
 */
function SuiteAccountSection({ user }: { user: User }) {
  const { data: config } = useAuthConfig()
  return (
    <section className="rounded-card bg-surface-container-low p-5">
      <div className="flex items-center gap-3">
        <Avatar name={user.display_name} size={44} />
        <div className="min-w-0 flex-1">
          <h2 className="text-body-large font-medium">{user.display_name}</h2>
          <p className="truncate text-body-small text-on-surface-variant">{user.email}</p>
        </div>
      </div>
      <p className="mt-4 text-body-medium text-on-surface-variant">
        {gettext(
          "Nome, email e password sono dell'account della suite ino: valgono per tutte le app e si cambiano su cornhub.",
        )}
      </p>
      {config && (
        <div className="mt-3 flex flex-wrap gap-2">
          <a className="btn-tonal btn-sm" href={config.account_url}>
            <Icon name="manage_accounts" size={18} />
            {gettext('Account della suite')}
          </a>
          <a className="btn-outlined btn-sm" href={config.ai_url}>
            <Icon name="key" size={18} />
            {gettext('Chiavi e limiti AI')}
          </a>
        </div>
      )}
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
