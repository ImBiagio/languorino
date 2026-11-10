import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'

import { useCompleteOnboarding, useProfile, useUpdateProfile } from '../../api/hooks'
import { LanguageSwitcher } from '../../components/LanguageSwitcher'
import { FoodPattern } from '../../components/illustrations'
import { ErrorBanner, Icon, Progress, Skeleton } from '../../components/ui'
import { ApiError } from '../../lib/api'
import { gettext, interpolate } from '../../lib/i18n'
import type { Profile, ProfileDraft } from '../../lib/types'
import { SECTIONS, changesFor, draftFrom, isDirty } from '../profile/sections'

/**
 * Il wizard del primo accesso: una sezione del profilo per passo. Ogni "Avanti"
 * salva il passo, cosi' chi chiude a meta' ritrova quello che ha scritto.
 */
export function OnboardingPage() {
  const { data: profile, error } = useProfile()
  if (error) return <ErrorBanner error={error} />
  if (!profile) return <Skeleton className="m-6 h-64" />
  if (profile.onboarding_completed) return <Navigate to="/" replace />
  return <Wizard profile={profile} />
}

function Wizard({ profile }: { profile: Profile }) {
  const navigate = useNavigate()
  const update = useUpdateProfile()
  const complete = useCompleteOnboarding()
  const [step, setStep] = useState(0)
  const [draft, setDraft] = useState<ProfileDraft>(() => draftFrom(profile))
  const [error, setError] = useState<unknown>(null)

  const section = SECTIONS[step]
  const last = step === SECTIONS.length - 1
  const busy = update.isPending || complete.isPending
  const errors = error instanceof ApiError ? error.fieldErrors() : {}

  const next = async () => {
    setError(null)
    try {
      if (section.fields.length && isDirty(draft, profile, section.fields)) {
        await update.mutateAsync(changesFor(draft, section.fields))
      }
      if (last) {
        await complete.mutateAsync()
        navigate('/', { replace: true })
        return
      }
      setStep(step + 1)
      window.scrollTo({ top: 0 })
    } catch (err) {
      setError(err)
    }
  }

  return (
    <div className="flex min-h-screen justify-center bg-surface-container-low px-4 py-6 sm:py-10">
      <div className="w-full max-w-xl">
        <div className="mb-5 flex items-center gap-3">
          <img src="/logo-mark.svg" alt="" width={40} height={40} className="h-10 w-10" />
          <p className="flex-1 text-title-medium">Languorino</p>
          <span className="text-body-medium text-on-surface-variant">
            {interpolate(gettext('Passo %s di %s'), [step + 1, SECTIONS.length])}
          </span>
        </div>
        <Progress
          value={step + 1}
          max={SECTIONS.length}
          label={gettext('Avanzamento del profilo')}
        />

        {step === 0 && (
          <Link
            to="/intervista"
            className="state mt-5 flex items-center gap-4 rounded-card bg-primary-container p-4 text-on-primary-container"
          >
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[14px] bg-primary text-on-primary">
              <Icon name="forum" size={24} />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-body-large font-medium">
                {gettext('Preferisci raccontarmelo?')}
              </span>
              <span className="block text-body-small opacity-80">
                {gettext('Due chiacchiere, anche a voce, al posto delle domande')}
              </span>
            </span>
            <Icon name="chevron_right" size={22} />
          </Link>
        )}

        <section className="card-elevated mt-5 overflow-hidden bg-surface">
          {/* Testata a doodle con l'icona del passo che ci si appoggia sopra. */}
          <div className="relative h-20 bg-primary-container">
            <FoodPattern opacity={0.9} />
            <span className="absolute -bottom-7 left-5 flex h-14 w-14 items-center justify-center rounded-[18px] bg-primary text-on-primary shadow-fab-mobile sm:left-8">
              <Icon name={section.icon} size={28} />
            </span>
          </div>
          <div className="p-5 pt-10 sm:p-8 sm:pt-11">
            <div className="mb-6">
              <h1 className="text-title-large">{section.title}</h1>
              <p className="text-body-medium text-on-surface-variant">{section.subtitle}</p>
            </div>

            <section.Component
              draft={draft}
              set={(changes) => setDraft((current) => ({ ...current, ...changes }))}
              errors={errors}
              profile={profile}
            />

            <div className="mt-6">
              <ErrorBanner error={error} />
            </div>
            <div className="mt-4 flex items-center gap-3">
              {step > 0 && (
                <button
                  type="button"
                  className="btn-text"
                  onClick={() => {
                    setError(null)
                    setStep(step - 1)
                  }}
                  disabled={busy}
                >
                  <Icon name="arrow_back" size={20} />
                  {gettext('Indietro')}
                </button>
              )}
              <span className="flex-1" />
              <button type="button" className="btn-filled" onClick={next} disabled={busy}>
                {last ? gettext('Inizia') : gettext('Avanti')}
                <Icon name={last ? 'check' : 'arrow_forward'} size={20} />
              </button>
            </div>
          </div>
        </section>

        <div className="mt-4 flex justify-center">
          <LanguageSwitcher />
        </div>
      </div>
    </div>
  )
}
