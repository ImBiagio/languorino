// Il riepilogo "Ho capito" dell'intervista, condiviso da chat e voce in tempo
// reale (ADR 0013, 0014): le proposte si accumulano qui e vanno nel profilo
// solo con "Salva nel profilo".

import clsx from 'clsx'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useAddPreference, useCompleteOnboarding, useUpdateProfile } from '../../api/hooks'
import { Chip, ErrorBanner, Icon } from '../../components/ui'
import { gettext, interpolate } from '../../lib/i18n'
import type { PreferenceKind, ProfileDraft } from '../../lib/types'
import { ACTIVITY_OPTIONS, GOAL_OPTIONS, MEAL_OPTIONS, SEX_OPTIONS } from '../profile/options'

export type PreferenceProposal = { kind: PreferenceKind; label: string; allergen: string }
export type ProposalResult = {
  updates?: Partial<ProfileDraft>
  preferences?: PreferenceProposal[]
}

const KIND_LABELS: Record<PreferenceKind, string> = {
  allergy: gettext('Allergia'),
  intolerance: gettext('Intolleranza'),
  like: gettext('Mi piace'),
  dislike: gettext('Non mi piace'),
}

/** Una riga leggibile per ogni campo proposto. */
function describe(key: string, value: unknown): string {
  switch (key) {
    case 'sex':
      return SEX_OPTIONS.find((option) => option.value === value)?.label ?? String(value)
    case 'height_cm':
      return interpolate(gettext('Altezza %s cm'), [String(value)])
    case 'weight_kg':
      return interpolate(gettext('Peso %s kg'), [String(value)])
    case 'goals':
      return (value as string[])
        .map((goal) => GOAL_OPTIONS.find((option) => option.value === goal)?.label ?? goal)
        .join(', ')
    case 'goals_note':
      return interpolate(gettext('Obiettivo: “%s”'), [String(value)])
    case 'activity_level':
      return interpolate(gettext('Attività: %s'), [
        ACTIVITY_OPTIONS.find((option) => option.value === value)?.label ?? String(value),
      ])
    case 'sport_sessions_per_week':
      return interpolate(gettext('Sport %s volte a settimana'), [String(value)])
    case 'conditions':
      return interpolate(gettext('Da considerare: %s'), [(value as string[]).join(', ')])
    case 'followed_by_nutritionist':
      return value ? gettext('Ti segue un nutrizionista') : gettext('Nessun nutrizionista')
    case 'meal_slots':
      return interpolate(gettext('Pasti: %s'), [
        (value as string[])
          .map((slot) => MEAL_OPTIONS.find((option) => option.value === slot)?.label ?? slot)
          .join(', '),
      ])
    case 'household_size':
      return interpolate(gettext('Cucini per %s'), [String(value)])
    default:
      return String(value)
  }
}

export function useProposals(onboarding: boolean) {
  const navigate = useNavigate()
  const update = useUpdateProfile()
  const addPreference = useAddPreference()
  const complete = useCompleteOnboarding()
  const [updates, setUpdates] = useState<Partial<ProfileDraft>>({})
  const [preferences, setPreferences] = useState<PreferenceProposal[]>([])
  const [finished, setFinished] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<unknown>(null)

  const merge = (result: ProposalResult) => {
    setUpdates((current) => ({ ...current, ...(result.updates ?? {}) }))
    setPreferences((current) => {
      const merged = [...current]
      for (const item of result.preferences ?? []) {
        const exists = merged.some(
          (other) =>
            other.kind === item.kind && other.label.toLowerCase() === item.label.toLowerCase(),
        )
        if (!exists) merged.push(item)
      }
      return merged
    })
  }

  const save = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      if (Object.keys(updates).length) await update.mutateAsync(updates)
      for (const item of preferences) {
        await addPreference.mutateAsync({
          kind: item.kind,
          label: item.label,
          allergen: item.allergen || undefined,
        })
      }
      if (onboarding) {
        await complete.mutateAsync()
        navigate('/', { replace: true })
      } else {
        navigate('/profilo', { replace: true })
      }
    } catch (error) {
      setSaveError(error)
    } finally {
      setSaving(false)
    }
  }

  return {
    onboarding,
    updates,
    setUpdates,
    preferences,
    setPreferences,
    count: Object.keys(updates).length + preferences.length,
    merge,
    finished,
    setFinished,
    save,
    saving,
    saveError,
  }
}

export type Proposals = ReturnType<typeof useProposals>

export function ProposalsPanel({ proposals }: { proposals: Proposals }) {
  const { updates, preferences, count, finished, onboarding } = proposals
  if (count === 0 && !finished) return null
  return (
    <section
      className={clsx(
        'mt-2 grid gap-3 rounded-card p-4',
        finished ? 'bg-primary-container text-on-primary-container' : 'bg-surface',
      )}
    >
      <h2 className="flex items-center gap-2 text-title-small">
        <Icon name="fact_check" size={20} />
        {finished ? gettext('Ecco cosa ho capito: controlla e salva') : gettext('Ho capito')}
      </h2>
      {count === 0 ? (
        <p className="text-body-medium">{gettext('Niente di nuovo da salvare.')}</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {Object.entries(updates).map(([key, value]) => (
            <Chip
              key={key}
              label={describe(key, value)}
              trailingIcon="close"
              onClick={() =>
                proposals.setUpdates((current) => {
                  const next = { ...current }
                  delete next[key as keyof ProfileDraft]
                  return next
                })
              }
            />
          ))}
          {preferences.map((item) => (
            <Chip
              key={`${item.kind}-${item.label}`}
              icon={
                item.kind === 'allergy' || item.kind === 'intolerance'
                  ? 'health_and_safety'
                  : item.kind === 'like'
                    ? 'favorite'
                    : 'thumb_down'
              }
              label={`${KIND_LABELS[item.kind]}: ${item.label}`}
              trailingIcon="close"
              onClick={() =>
                proposals.setPreferences((current) => current.filter((other) => other !== item))
              }
            />
          ))}
        </div>
      )}
      <ErrorBanner error={proposals.saveError} />
      <div className="flex flex-wrap justify-end gap-2">
        {!finished && (
          <button type="button" className="btn-text" onClick={() => proposals.setFinished(true)}>
            {gettext('Basta così')}
          </button>
        )}
        <button
          type="button"
          className="btn-filled"
          disabled={proposals.saving || (count === 0 && !onboarding)}
          onClick={proposals.save}
        >
          <Icon name="check" size={20} />
          {onboarding ? gettext('Salva e inizia') : gettext('Salva nel profilo')}
        </button>
      </div>
    </section>
  )
}
