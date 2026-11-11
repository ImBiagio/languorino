import { Link } from 'react-router-dom'

import { useCurrentPlan, useProfile } from '../../api/hooks'
import { Page } from '../../components/Layout'
import { EmptyPlateIllustration, FoodPattern } from '../../components/illustrations'
import { Chip, EmptyState, Icon } from '../../components/ui'
import { useAuth } from '../../lib/auth'
import { gettext, interpolate, intlLocale } from '../../lib/i18n'
import { addDays, formatDayLong, formatWeekday, todayIso } from '../plans/dates'
import { MealRow } from '../plans/PlanPages'
import { GOAL_OPTIONS, preferenceLabel } from '../profile/options'

/**
 * "Oggi": qui finiranno i pasti di oggi e la prossima sessione di prep. Finche'
 * non c'e' un piano mostra cosa l'app sa dell'utente, per controllarlo subito.
 */
export function HomePage() {
  const { user } = useAuth()
  const { data: profile } = useProfile()
  const { data: plan } = useCurrentPlan()
  const today = todayIso()
  const tomorrow = addDays(today, 1)
  const order = ['breakfast', 'morning_snack', 'lunch', 'afternoon_snack', 'dinner']
  const mealsOf = (day: string) =>
    (plan?.meals ?? [])
      .filter((meal) => meal.date === day)
      .sort((a, b) => order.indexOf(a.slot) - order.indexOf(b.slot))
  // Cosa si cucina oggi per i giorni dopo (meal prep).
  const prepToday = (plan?.meals ?? []).filter(
    (meal) => meal.cooked_on === today && meal.date !== today && meal.recipe,
  )
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
        <Link
          to="/cosa-cucino"
          className="state flex items-center gap-4 rounded-card bg-primary-container p-4 text-on-primary-container"
        >
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-[16px] bg-primary text-on-primary">
            <Icon name="skillet" size={26} />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-title-medium">{gettext('Cosa cucino oggi?')}</span>
            <span className="block text-body-small opacity-80">
              {gettext('Dimmi cosa hai in casa o fotografa il frigo')}
            </span>
          </span>
          <Icon name="chevron_right" size={22} />
        </Link>
        <Link
          to="/chiedi"
          className="state flex items-center gap-4 rounded-card bg-surface-container-low p-4 text-on-surface"
        >
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-[16px] bg-secondary-container text-on-secondary-container">
            <Icon name="forum" size={26} />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-title-medium">{gettext('Chiedi a Languorino')}</span>
            <span className="block text-body-small text-on-surface-variant">
              {gettext('Quanto ne mangio a pranzo e cena? Cosa ceno domani?')}
            </span>
          </span>
          <Icon name="chevron_right" size={22} />
        </Link>
        {plan ? (
          <>
            {[today, tomorrow].map((day) => {
              const meals = mealsOf(day)
              if (!meals.length) return null
              return (
                <section key={day} className="rounded-card bg-surface-container-low p-4">
                  <header className="mb-2 flex items-center justify-between gap-2">
                    <h2 className="text-title-medium">
                      {day === today ? gettext('Oggi mangi') : gettext('Domani')}
                    </h2>
                    <Link to={`/piano/${plan.id}`} className="btn-text btn-sm">
                      {gettext('Tutto il piano')}
                      <Icon name="chevron_right" size={18} />
                    </Link>
                  </header>
                  <ul className="grid gap-2">
                    {meals.map((meal) => (
                      <MealRow key={meal.id} meal={meal} />
                    ))}
                  </ul>
                </section>
              )
            })}
            {plan.start_date > tomorrow && (
              <Link
                to={`/piano/${plan.id}`}
                className="state flex items-center gap-4 rounded-card bg-surface-container-low p-5"
              >
                <Icon name="event_upcoming" size={28} className="text-primary" />
                <span className="min-w-0 flex-1">
                  <span className="block text-title-medium">
                    {interpolate(gettext('Il tuo piano parte %s'), [
                      formatDayLong(plan.start_date).toLowerCase(),
                    ])}
                  </span>
                  <span className="block text-body-small text-on-surface-variant">
                    {gettext('Guarda cosa preparare per iniziare')}
                  </span>
                </span>
                <Icon name="chevron_right" size={22} />
              </Link>
            )}
            {prepToday.length > 0 && (
              <section className="rounded-card bg-primary-container p-4 text-on-primary-container">
                <h2 className="mb-2 flex items-center gap-2 text-title-medium">
                  <Icon name="kitchen" size={22} />
                  {gettext('Oggi prepari anche')}
                </h2>
                <ul className="grid gap-1 text-body-medium">
                  {prepToday.map((meal) => (
                    <li key={meal.id}>
                      <Link
                        to={`/ricette/${meal.recipe!.id}`}
                        className="font-medium hover:underline"
                      >
                        {meal.recipe!.title}
                      </Link>{' '}
                      {interpolate(gettext('per %s'), [formatWeekday(meal.date)])}
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </>
        ) : (
          <EmptyState
            illustration={<EmptyPlateIllustration />}
            title={gettext('Ancora nessun piano')}
            description={gettext(
              'Quando avrai un piano alimentare, qui troverai i pasti di oggi e di domani e cosa preparare.',
            )}
            action={
              <Link to="/piano/nuovo" className="btn-filled">
                <Icon name="auto_awesome" size={20} />
                {gettext('Crea il piano')}
              </Link>
            }
          />
        )}
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
