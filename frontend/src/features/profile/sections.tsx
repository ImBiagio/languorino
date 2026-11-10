// Le sezioni del profilo alimentare. Le stesse servono al wizard (un passo per
// sezione) e alla pagina Profilo (una card per sezione): cosi' quello che si
// chiede all'inizio e quello che si modifica dopo non possono divergere.
//
// Due tipi di campi: quelli del profilo vanno in una bozza e si salvano con
// PATCH quando si va avanti (o con "Salva"); le preferenze (gusti, allergie,
// intolleranze) hanno la loro API e si salvano a ogni tocco.

import clsx from 'clsx'
import type { ComponentType } from 'react'

import { useAddPreference, useRemovePreference } from '../../api/hooks'
import { ChipEditor, Chip, ErrorBanner, Field, Icon, Stepper } from '../../components/ui'
import { gettext, interpolate, ngettext } from '../../lib/i18n'
import type { FoodPreference, PreferenceKind, Profile, ProfileDraft } from '../../lib/types'
import {
  ACTIVITY_OPTIONS,
  ALLERGEN_OPTIONS,
  CONDITION_SUGGESTIONS,
  DISLIKE_SUGGESTIONS,
  GOAL_OPTIONS,
  INTOLERANCE_SUGGESTIONS,
  LIKE_SUGGESTIONS,
  MEAL_OPTIONS,
  SEX_OPTIONS,
  isAllergenChip,
} from './options'

export interface SectionProps {
  draft: ProfileDraft
  set: (changes: Partial<ProfileDraft>) => void
  errors: Record<string, string>
  profile: Profile
}

export interface SectionDef {
  id: string
  title: string
  subtitle: string
  icon: string
  /** I campi della bozza che questa sezione salva; vuoto = solo preferenze. */
  fields: (keyof ProfileDraft)[]
  Component: ComponentType<SectionProps>
}

/* ----------------------------------------------------------- bozza ---- */

/** Le chiavi della bozza: tutto il profilo tranne i campi calcolati dal server. */
const DRAFT_FIELDS: (keyof ProfileDraft)[] = [
  'first_name',
  'last_name',
  'birth_date',
  'sex',
  'height_cm',
  'weight_kg',
  'goals',
  'goals_note',
  'activity_level',
  'sport_sessions_per_week',
  'conditions',
  'followed_by_nutritionist',
  'meal_slots',
  'household_size',
]

function pick(source: ProfileDraft, fields: (keyof ProfileDraft)[]): Partial<ProfileDraft> {
  return Object.fromEntries(fields.map((field) => [field, source[field]]))
}

export function draftFrom(profile: Profile): ProfileDraft {
  return pick(profile, DRAFT_FIELDS) as ProfileDraft
}

/** Solo i campi della sezione, pronti per il PATCH (il peso accetta la virgola). */
export function changesFor(draft: ProfileDraft, fields: (keyof ProfileDraft)[]) {
  const changes = pick(draft, fields)
  if ('weight_kg' in changes) {
    const raw = (changes.weight_kg ?? '').toString().replace(',', '.').trim()
    changes.weight_kg = raw ? raw : null
  }
  return changes
}

export function isDirty(draft: ProfileDraft, profile: Profile, fields: (keyof ProfileDraft)[]) {
  const saved = draftFrom(profile)
  return fields.some((field) => JSON.stringify(draft[field]) !== JSON.stringify(saved[field]))
}

/* ------------------------------------------------------- mattoncini ---- */

function Question({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="mb-3">
      <h3 className="text-body-large font-medium">{title}</h3>
      {hint && <p className="text-body-small text-on-surface-variant">{hint}</p>}
    </div>
  )
}

/** Card selezionabile, per le scelte che hanno bisogno di una riga di spiegazione. */
function OptionCard({
  selected,
  onClick,
  icon,
  label,
  hint,
}: {
  selected: boolean
  onClick: () => void
  icon?: string
  label: string
  hint?: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={clsx(
        'state flex w-full items-center gap-3 rounded-row px-4 py-3 text-left transition',
        selected
          ? 'bg-primary-container text-on-primary-container'
          : 'bg-surface-container text-on-surface',
      )}
    >
      {icon && <Icon name={icon} size={24} filled={selected} />}
      <span className="min-w-0 flex-1">
        <span className="block text-body-large font-medium">{label}</span>
        {hint && (
          <span
            className={clsx(
              'block text-body-small',
              selected ? 'text-on-primary-container' : 'text-on-surface-variant',
            )}
          >
            {hint}
          </span>
        )}
      </span>
      {/* Lo spazio dell'icona c'e' sempre: selezionare non manda a capo il testo. */}
      <Icon
        name="check_circle"
        size={22}
        filled
        className={clsx('shrink-0', !selected && 'invisible')}
      />
    </button>
  )
}

function toggle<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((item) => item !== value) : [...list, value]
}

/** Le preferenze di un tipo come voci per ChipEditor, con aggiunta e rimozione. */
function usePreferenceList(profile: Profile, kind: PreferenceKind) {
  const add = useAddPreference()
  const remove = useRemovePreference()
  const items = profile.preferences.filter((item) => item.kind === kind)
  return {
    items: items.map((item) => ({ key: item.id, label: item.label })),
    onAdd: (label: string) => add.mutate({ kind, label }),
    onRemove: (id: string) => remove.mutate(id),
    error: add.error ?? remove.error,
  }
}

/* --------------------------------------------------------- sezioni ---- */

function AboutSection({ draft, set, errors }: SectionProps) {
  const today = new Date().toISOString().slice(0, 10)
  return (
    <div className="grid gap-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={gettext('Nome')} error={errors.first_name}>
          <input
            className="field-input"
            autoComplete="given-name"
            value={draft.first_name}
            maxLength={80}
            onChange={(event) => set({ first_name: event.target.value })}
          />
        </Field>
        <Field label={gettext('Cognome')} error={errors.last_name}>
          <input
            className="field-input"
            autoComplete="family-name"
            value={draft.last_name}
            maxLength={80}
            onChange={(event) => set({ last_name: event.target.value })}
          />
        </Field>
      </div>
      <Field
        label={gettext('Data di nascita')}
        error={errors.birth_date}
        hint={gettext('Serve a calcolare quanto ti serve: l’età cambia il fabbisogno.')}
      >
        <input
          className="field-input"
          type="date"
          autoComplete="bday"
          max={today}
          min="1900-01-01"
          value={draft.birth_date ?? ''}
          onChange={(event) => set({ birth_date: event.target.value || null })}
        />
      </Field>
      <div>
        <Question title={gettext('Sesso')} />
        <div className="flex flex-wrap gap-2">
          {SEX_OPTIONS.map((option) => (
            <Chip
              key={option.value}
              label={option.label}
              selected={draft.sex === option.value}
              onClick={() => set({ sex: draft.sex === option.value ? '' : option.value })}
            />
          ))}
        </div>
        {errors.sex && <p className="mt-1 text-body-small text-error">{errors.sex}</p>}
      </div>
    </div>
  )
}

function BodySection({ draft, set, errors }: SectionProps) {
  return (
    <div className="grid gap-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={gettext('Altezza (cm)')} error={errors.height_cm}>
          <input
            className="field-input"
            type="number"
            inputMode="numeric"
            min={80}
            max={250}
            value={draft.height_cm ?? ''}
            onChange={(event) =>
              set({ height_cm: event.target.value ? Number(event.target.value) : null })
            }
          />
        </Field>
        <Field label={gettext('Peso (kg)')} error={errors.weight_kg}>
          <input
            className="field-input"
            inputMode="decimal"
            value={draft.weight_kg ?? ''}
            onChange={(event) =>
              set({ weight_kg: event.target.value.replace(/[^\d.,]/g, '') || null })
            }
          />
        </Field>
      </div>
      <p className="flex items-start gap-2 text-body-small text-on-surface-variant">
        <Icon name="lock" size={18} />
        {gettext(
          'Altezza e peso servono solo a calibrare le porzioni del piano. Restano tuoi e non si condividono.',
        )}
      </p>
    </div>
  )
}

function GoalsSection({ draft, set, errors }: SectionProps) {
  return (
    <div className="grid gap-4">
      <div className="grid gap-2 sm:grid-cols-2">
        {GOAL_OPTIONS.map((option) => (
          <OptionCard
            key={option.value}
            icon={option.icon}
            label={option.label}
            selected={draft.goals.includes(option.value)}
            onClick={() => set({ goals: toggle(draft.goals, option.value) })}
          />
        ))}
      </div>
      <Field
        label={gettext('Altro da dire?')}
        error={errors.goals_note}
        hint={gettext('Es. “Voglio arrivare in forma alla maratona di aprile”.')}
      >
        <textarea
          className="field-input min-h-[72px] resize-y"
          maxLength={1000}
          value={draft.goals_note}
          onChange={(event) => set({ goals_note: event.target.value })}
        />
      </Field>
    </div>
  )
}

function LifestyleSection({ draft, set }: SectionProps) {
  const sessions = draft.sport_sessions_per_week ?? 0
  return (
    <div className="grid gap-6">
      <div>
        <Question title={gettext('Quanto ti muovi durante il giorno?')} />
        <div className="grid gap-2">
          {ACTIVITY_OPTIONS.map((option) => (
            <OptionCard
              key={option.value}
              label={option.label}
              hint={option.hint}
              selected={draft.activity_level === option.value}
              onClick={() => set({ activity_level: option.value })}
            />
          ))}
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Question
          title={gettext('Sport a settimana')}
          hint={gettext('Allenamenti, corse, partite: quante volte di solito.')}
        />
        <Stepper
          label={gettext('Sport a settimana')}
          value={sessions}
          min={0}
          max={14}
          onChange={(value) => set({ sport_sessions_per_week: value })}
          format={(value) =>
            value === 0
              ? gettext('Mai')
              : interpolate(ngettext('%s volta', '%s volte', value), [value])
          }
        />
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Question
          title={gettext('Per quante persone cucini?')}
          hint={gettext('Di solito, te compreso. Cambia porzioni e spesa.')}
        />
        <Stepper
          label={gettext('Per quante persone cucini?')}
          value={draft.household_size}
          min={1}
          max={12}
          onChange={(value) => set({ household_size: value })}
        />
      </div>
    </div>
  )
}

function RestrictionsSection({ draft, set, profile }: SectionProps) {
  const add = useAddPreference()
  const remove = useRemovePreference()
  const allergies = profile.preferences.filter((item) => item.kind === 'allergy')
  // I chip salvano il codice dell'allergene come etichetta (vedi
  // isAllergenChip): cosi' "gamberetti", scritto a mano e collegato ai
  // crostacei, non accende il chip "Crostacei" e toccarlo non lo cancella.
  const byAllergen = new Map<string, FoodPreference>()
  for (const item of allergies) if (isAllergenChip(item)) byAllergen.set(item.allergen, item)
  const otherAllergies = allergies.filter((item) => !isAllergenChip(item))
  const intolerances = usePreferenceList(profile, 'intolerance')

  return (
    <div className="grid gap-6">
      <div>
        <Question
          title={gettext('Allergie')}
          hint={gettext('Le ricette con questi ingredienti non entreranno mai nel tuo piano.')}
        />
        <div className="flex flex-wrap gap-2">
          {ALLERGEN_OPTIONS.map((option) => {
            const current = byAllergen.get(option.value)
            return (
              <Chip
                key={option.value}
                label={option.label}
                selected={Boolean(current)}
                icon={current ? 'check' : undefined}
                onClick={() =>
                  current
                    ? remove.mutate(current.id)
                    : add.mutate({ kind: 'allergy', label: option.value, allergen: option.value })
                }
              />
            )
          })}
        </div>
        <div className="mt-3">
          <ChipEditor
            inputLabel={gettext('Altra allergia (es. kiwi, pesche)')}
            items={otherAllergies.map((item) => ({ key: item.id, label: item.label }))}
            onAdd={(label) => add.mutate({ kind: 'allergy', label })}
            onRemove={(id) => remove.mutate(id)}
          />
        </div>
      </div>

      <div>
        <Question title={gettext('Intolleranze')} />
        <ChipEditor
          inputLabel={gettext('Aggiungi un’intolleranza')}
          suggestions={INTOLERANCE_SUGGESTIONS}
          items={intolerances.items}
          onAdd={intolerances.onAdd}
          onRemove={intolerances.onRemove}
        />
      </div>

      <div>
        <Question
          title={gettext('Patologie')}
          hint={gettext('Condizioni di cui il piano deve tenere conto.')}
        />
        <ChipEditor
          inputLabel={gettext('Aggiungi una patologia')}
          suggestions={CONDITION_SUGGESTIONS}
          items={draft.conditions.map((label) => ({ key: label, label }))}
          onAdd={(label) => set({ conditions: [...draft.conditions, label] })}
          onRemove={(label) => set({ conditions: draft.conditions.filter((c) => c !== label) })}
        />
      </div>

      <p className="flex items-start gap-2 rounded-row bg-warning-container px-4 py-3 text-body-small text-on-warning-container">
        <Icon name="medical_information" size={20} />
        {gettext(
          'Languorino ti aiuta a organizzarti ma non sostituisce medico o nutrizionista: con una patologia segui sempre le loro indicazioni.',
        )}
      </p>
      <ErrorBanner error={add.error ?? remove.error ?? intolerances.error} />
    </div>
  )
}

function TastesSection({ profile }: SectionProps) {
  const likes = usePreferenceList(profile, 'like')
  const dislikes = usePreferenceList(profile, 'dislike')
  return (
    <div className="grid gap-6">
      <div>
        <Question
          title={gettext('Cosa ti piace')}
          hint={gettext('Piatti, ingredienti, cucine: il piano li proporrà più spesso.')}
        />
        <ChipEditor
          inputLabel={gettext('Aggiungi qualcosa che ti piace')}
          suggestions={LIKE_SUGGESTIONS}
          items={likes.items}
          onAdd={likes.onAdd}
          onRemove={likes.onRemove}
        />
      </div>
      <div>
        <Question
          title={gettext('Cosa non ti piace')}
          hint={gettext('Non è un’allergia: il piano li eviterà quando può.')}
        />
        <ChipEditor
          inputLabel={gettext('Aggiungi qualcosa che non ti piace')}
          suggestions={DISLIKE_SUGGESTIONS}
          items={dislikes.items}
          onAdd={dislikes.onAdd}
          onRemove={dislikes.onRemove}
        />
      </div>
      <ErrorBanner error={likes.error ?? dislikes.error} />
    </div>
  )
}

function MealsSection({ draft, set, errors }: SectionProps) {
  return (
    <div className="grid gap-6">
      <div>
        <Question title={gettext('Ti segue un nutrizionista?')} />
        <div className="grid gap-2 sm:grid-cols-2">
          <OptionCard
            icon="stethoscope"
            label={gettext('Sì')}
            hint={gettext('Più avanti potrai caricare il suo piano.')}
            selected={draft.followed_by_nutritionist === true}
            onClick={() => set({ followed_by_nutritionist: true })}
          />
          <OptionCard
            icon="auto_awesome"
            label={gettext('No')}
            hint={gettext('Il piano lo costruiamo insieme dai tuoi obiettivi.')}
            selected={draft.followed_by_nutritionist === false}
            onClick={() => set({ followed_by_nutritionist: false })}
          />
        </div>
      </div>
      <div>
        <Question
          title={gettext('Quali pasti vuoi nel piano?')}
          hint={gettext('Puoi cambiarli per ogni piano.')}
        />
        <div className="grid gap-2">
          {MEAL_OPTIONS.map((option) => (
            <OptionCard
              key={option.value}
              icon={option.icon}
              label={option.label}
              selected={draft.meal_slots.includes(option.value)}
              onClick={() => set({ meal_slots: toggle(draft.meal_slots, option.value) })}
            />
          ))}
        </div>
        {errors.meal_slots && (
          <p className="mt-1 text-body-small text-error">{errors.meal_slots}</p>
        )}
      </div>
    </div>
  )
}

export const SECTIONS: SectionDef[] = [
  {
    id: 'about',
    title: gettext('Chi sei'),
    subtitle: gettext('Due minuti per conoscerti: puoi lasciare vuoto quello che non vuoi dire.'),
    icon: 'badge',
    fields: ['first_name', 'last_name', 'birth_date', 'sex'],
    Component: AboutSection,
  },
  {
    id: 'body',
    title: gettext('Altezza e peso'),
    subtitle: gettext('Per porzioni giuste, né troppo né poco.'),
    icon: 'straighten',
    fields: ['height_cm', 'weight_kg'],
    Component: BodySection,
  },
  {
    id: 'goals',
    title: gettext('I tuoi obiettivi'),
    subtitle: gettext('Cosa vuoi ottenere mangiando meglio? Scegli tutto quello che vale.'),
    icon: 'flag',
    fields: ['goals', 'goals_note'],
    Component: GoalsSection,
  },
  {
    id: 'lifestyle',
    title: gettext('Stile di vita'),
    subtitle: gettext('Quanto ti muovi e per quanti cucini.'),
    icon: 'directions_run',
    fields: ['activity_level', 'sport_sessions_per_week', 'household_size'],
    Component: LifestyleSection,
  },
  {
    id: 'restrictions',
    title: gettext('Allergie e salute'),
    subtitle: gettext('Quello che non puoi mangiare, e di cosa tenere conto.'),
    icon: 'health_and_safety',
    fields: ['conditions'],
    Component: RestrictionsSection,
  },
  {
    id: 'tastes',
    title: gettext('I tuoi gusti'),
    subtitle: gettext('Cosa ami e cosa preferisci evitare.'),
    icon: 'favorite',
    fields: [],
    Component: TastesSection,
  },
  {
    id: 'meals',
    title: gettext('Pasti e nutrizionista'),
    subtitle: gettext('L’ultima cosa: come vuoi organizzare la giornata.'),
    icon: 'restaurant',
    fields: ['followed_by_nutritionist', 'meal_slots'],
    Component: MealsSection,
  },
]
