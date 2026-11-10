import { Link } from 'react-router-dom'

import { useProfile } from '../../api/hooks'
import { Page } from '../../components/Layout'
import { EmptyPlateIllustration, FoodPattern } from '../../components/illustrations'
import { Chip, EmptyState, Icon } from '../../components/ui'
import { useAuth } from '../../lib/auth'
import { gettext, interpolate, intlLocale } from '../../lib/i18n'
import { GOAL_OPTIONS, preferenceLabel } from '../profile/options'

/**
 * "Oggi": qui finiranno i pasti di oggi e la prossima sessione di prep. Finche'
 * non c'e' un piano mostra cosa l'app sa dell'utente, per controllarlo subito.
 */
export function HomePage() {
  const { user } = useAuth()
  const { data: profile } = useProfile()
  const restrictions =
    profile?.preferences.filter((item) => item.kind === 'allergy' || item.kind === 'intolerance') ??
    []
  const goals = GOAL_OPTIONS.filter((option) => profile?.goals.includes(option.value))

  return (
    <Page>
      <div className="grid gap-4 px-5 pt-5 md:px-8 md:pt-8">
        {/* Benvenuto: la sola superficie piena di blu della pagina. */}
        <header className="relative overflow-hidden rounded-panel bg-primary px-6 py-7 text-on-primary md:px-8 md:py-9">
          <FoodPattern tone="dark" opacity={0.35} />
          <div className="relative">
            <p className="text-body-large opacity-90">{todayLabel()}</p>
            <h1 className="mt-1 text-[28px] font-medium leading-9 md:text-headline-small">
              {interpolate(gettext('Ciao %s'), [user?.display_name ?? ''])}
            </h1>
            <p className="mt-1 text-body-large opacity-90">{gettext('Cosa mangiamo oggi?')}</p>
          </div>
        </header>
        <EmptyState
          illustration={<EmptyPlateIllustration />}
          title={gettext('Ancora nessun piano')}
          description={gettext(
            'Quando avrai un piano alimentare, qui troverai i pasti di oggi e di domani e cosa preparare.',
          )}
        />
        {profile && (
          <section className="rounded-card bg-surface-container-low p-5">
            <header className="mb-3 flex items-center gap-3">
              <h2 className="flex-1 text-body-large font-medium">{gettext('Cosa so di te')}</h2>
              <Link to="/profilo" className="btn-text btn-sm">
                {gettext('Modifica')}
                <Icon name="chevron_right" size={18} />
              </Link>
            </header>
            <div className="grid gap-3">
              <SummaryRow icon="flag" label={gettext('Obiettivi')}>
                {goals.length
                  ? goals.map((goal) => (
                      <Chip key={goal.value} variant="assist" label={goal.label} />
                    ))
                  : null}
              </SummaryRow>
              <SummaryRow icon="health_and_safety" label={gettext('Da evitare per forza')}>
                {restrictions.length
                  ? restrictions.map((item) => (
                      <Chip key={item.id} variant="assist" label={preferenceLabel(item)} />
                    ))
                  : null}
              </SummaryRow>
            </div>
          </section>
        )}
      </div>
    </Page>
  )
}

function SummaryRow({
  icon,
  label,
  children,
}: {
  icon: string
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="flex items-start gap-3">
      <Icon name={icon} size={20} className="mt-2 text-on-surface-variant" />
      <div className="min-w-0 flex-1">
        <p className="text-label-small text-on-surface-variant">{label}</p>
        <div className="mt-1 flex flex-wrap gap-2">
          {children ?? <span className="text-body-medium">{gettext('Niente')}</span>}
        </div>
      </div>
    </div>
  )
}

/** "lunedì 10 novembre", nella lingua dell'interfaccia. */
function todayLabel(): string {
  const label = new Intl.DateTimeFormat(intlLocale(), {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  }).format(new Date())
  return label.charAt(0).toUpperCase() + label.slice(1)
}
