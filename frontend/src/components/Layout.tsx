import clsx from 'clsx'
import type { ReactNode } from 'react'
import { NavLink, Outlet } from 'react-router-dom'

import { gettext } from '../lib/i18n'
import { Icon } from './ui'

interface Destination {
  to: string
  label: string
  icon: string
  end?: boolean
}

/** Poche sezioni, sempre tutte visibili: rail su desktop, barra in basso su mobile. */
const DESTINATIONS: Destination[] = [
  { to: '/', label: gettext('Oggi'), icon: 'today', end: true },
  { to: '/profilo', label: gettext('Profilo'), icon: 'person' },
]

export function AppLayout() {
  // Contatori da mostrare sulle voci (es. non letti): percorso -> numero.
  const badges: Record<string, number> = {}
  return (
    <div className="flex min-h-screen bg-surface">
      {/* --- navigation rail (desktop) --- */}
      <nav
        aria-label={gettext('Sezioni')}
        className="sticky top-0 z-40 hidden h-screen w-24 shrink-0 flex-col items-center bg-surface-container-low py-5 md:flex"
      >
        <img src="/logo-mark.svg" alt="Languorino" width={48} height={48} className="h-12 w-12" />
        <div className="mt-8 flex flex-col items-center gap-3.5">
          {DESTINATIONS.map((destination) => (
            <NavItem
              key={destination.to}
              destination={destination}
              badge={badges[destination.to]}
            />
          ))}
        </div>
      </nav>

      {/* Su mobile lo spazio in fondo supera barra e FAB, che sta a 104px + 56px. */}
      <main className="min-w-0 flex-1 pb-44 md:pb-24">
        <Outlet />
      </main>

      {/* --- bottom bar (mobile) --- */}
      <nav
        aria-label={gettext('Sezioni')}
        className="safe-bottom fixed inset-x-0 bottom-0 z-30 flex justify-around bg-surface-container-low px-2 pt-3 md:hidden"
      >
        {DESTINATIONS.map((destination) => (
          <NavItem
            key={destination.to}
            destination={destination}
            badge={badges[destination.to]}
            grow
          />
        ))}
      </nav>
    </div>
  )
}

function NavItem({
  destination,
  grow,
  badge,
}: {
  destination: Destination
  grow?: boolean
  /** Quanti non letti: il pallino con il numero sull'icona. */
  badge?: number
}) {
  return (
    <NavLink
      to={destination.to}
      end={destination.end}
      className={clsx('flex flex-col items-center gap-1', grow && 'flex-1')}
    >
      {({ isActive }) => (
        <>
          <span
            className={clsx(
              'state relative flex items-center justify-center transition-colors duration-200 ease-m3',
              isActive
                ? 'bg-secondary-container text-on-secondary-container'
                : 'text-on-surface-variant',
            )}
            style={{ width: 56, height: 32, borderRadius: 16 }}
          >
            <Icon name={destination.icon} size={24} filled={isActive} />
            {badge ? (
              <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-pill bg-error px-1 text-[11px] font-medium leading-none text-white">
                {badge > 99 ? '99+' : badge}
              </span>
            ) : null}
          </span>
          <span
            className={clsx(
              'text-center text-label-small',
              isActive ? 'text-on-surface' : 'text-on-surface-variant',
            )}
          >
            {destination.label}
          </span>
        </>
      )}
    </NavLink>
  )
}

/**
 * Il contenitore di ogni pagina: centrato e largo uguale dappertutto, col
 * testo che resta a sinistra. Senza, su schermi larghi una pagina si allargava a tutto lo
 * schermo e un'altra no, e le sezioni avevano larghezze diverse.
 */
export function Page({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={clsx('mx-auto w-full max-w-5xl', className)}>{children}</div>
}

/** Intestazione di pagina: titolo grande, sottotitolo, azioni a destra. */
export function PageHeader({
  title,
  subtitle,
  back,
  actions,
}: {
  title: string
  subtitle?: string
  back?: { to: string; label: string }
  actions?: ReactNode
}) {
  return (
    <header className="px-5 pb-4 pt-5 md:px-8 md:pt-8">
      {back && (
        <NavLink to={back.to} className="btn-text btn-sm -ml-3 mb-2">
          <Icon name="arrow_back" size={20} />
          {back.label}
        </NavLink>
      )}
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <h1 className="break-words text-[28px] font-medium leading-9 md:text-headline-small">
            {title}
          </h1>
          {subtitle && <p className="mt-1 text-body-medium text-on-surface-variant">{subtitle}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </header>
  )
}
