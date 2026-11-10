import clsx from 'clsx'
import type { Dispatch, SetStateAction } from 'react'
import { useEffect, useRef, useState } from 'react'

import { useIngredientSearch, useTags } from '../../api/hooks'
import {
  Chip,
  ChipEditor,
  Field,
  Icon,
  IconButton,
  Segmented,
  Stepper,
  Switch,
} from '../../components/ui'
import { useClickOutside } from '../../lib/hooks'
import { gettext, interpolate, ngettext } from '../../lib/i18n'
import type {
  Difficulty,
  ImportedRecipeDraft,
  Ingredient,
  MealSlot,
  Recipe,
  RecipePayload,
  Unit,
  UUID,
} from '../../lib/types'
import { MEAL_OPTIONS } from '../profile/options'
import { CATEGORY_LABELS, DIFFICULTY_OPTIONS, UNIT_OPTIONS, unitLabel } from './options'

/** Una riga di ingrediente nel form. `key` serve solo a React. */
export interface LineDraft {
  key: string
  ingredient_id: UUID | null
  /** Il reparto quando la riga e' collegata al catalogo, per il suggerimento sotto. */
  category: string | null
  name: string
  quantity: string
  unit: Unit
  note: string
  optional: boolean
}

export interface Draft {
  title: string
  description: string
  servings: number
  prep_minutes: string
  cook_minutes: string
  difficulty: Difficulty
  meal_slots: MealSlot[]
  steps: string[]
  keeps_days: number | null
  freezable: boolean
  tags: string[]
  lines: LineDraft[]
}

let nextKey = 0
const newKey = () => `line-${nextKey++}`

export function emptyLine(): LineDraft {
  return {
    key: newKey(),
    ingredient_id: null,
    category: null,
    name: '',
    quantity: '',
    unit: 'g',
    note: '',
    optional: false,
  }
}

export function draftFromRecipe(recipe?: Recipe): Draft {
  if (!recipe) {
    return {
      title: '',
      description: '',
      servings: 2,
      prep_minutes: '',
      cook_minutes: '',
      difficulty: 'easy',
      meal_slots: [],
      steps: [''],
      keeps_days: null,
      freezable: false,
      tags: [],
      lines: [emptyLine(), emptyLine(), emptyLine()],
    }
  }
  return {
    title: recipe.title,
    description: recipe.description,
    servings: recipe.servings,
    prep_minutes: recipe.prep_minutes ? String(recipe.prep_minutes) : '',
    cook_minutes: recipe.cook_minutes ? String(recipe.cook_minutes) : '',
    difficulty: recipe.difficulty,
    meal_slots: recipe.meal_slots,
    steps: recipe.steps.length ? recipe.steps : [''],
    keeps_days: recipe.keeps_days,
    freezable: recipe.freezable,
    tags: recipe.tags,
    lines: recipe.ingredients.length
      ? recipe.ingredients.map((line) => ({
          key: newKey(),
          ingredient_id: line.ingredient.id,
          category: line.ingredient.category,
          name: line.ingredient.name,
          // Nel campo la virgola, come la scriverebbe chi usa l'app in italiano.
          quantity: line.quantity === null ? '' : String(Number(line.quantity)),
          unit: line.unit,
          note: line.note,
          optional: line.optional,
        }))
      : [emptyLine()],
  }
}

export function payloadFrom(draft: Draft): RecipePayload {
  const minutes = (raw: string) => (raw.trim() ? Math.max(0, Math.round(Number(raw))) : 0)
  return {
    title: draft.title,
    description: draft.description.trim(),
    servings: draft.servings,
    prep_minutes: minutes(draft.prep_minutes),
    cook_minutes: minutes(draft.cook_minutes),
    difficulty: draft.difficulty,
    meal_slots: draft.meal_slots,
    steps: draft.steps,
    keeps_days: draft.keeps_days,
    freezable: draft.freezable,
    tags: draft.tags,
    // Le righe lasciate vuote non si mandano.
    ingredients: draft.lines
      .filter((line) => line.name.trim())
      .map((line) => {
        const quantity = line.quantity.replace(',', '.').trim()
        return {
          ingredient_id: line.ingredient_id,
          name: line.ingredient_id ? undefined : line.name.trim(),
          quantity: quantity && line.unit !== 'to_taste' ? quantity : null,
          unit: line.unit,
          note: line.note,
          optional: line.optional,
        }
      }),
  }
}

/** Una ricetta letta da foto o PDF (``Job.result.recipes``) come bozza del form. */
export function draftFromImport(imported: ImportedRecipeDraft): Draft {
  return {
    title: imported.title,
    description: imported.description,
    servings: imported.servings,
    prep_minutes: imported.prep_minutes ? String(imported.prep_minutes) : '',
    cook_minutes: imported.cook_minutes ? String(imported.cook_minutes) : '',
    difficulty: imported.difficulty,
    meal_slots: imported.meal_slots,
    steps: imported.steps.length ? imported.steps : [''],
    keeps_days: imported.keeps_days,
    freezable: imported.freezable,
    tags: imported.tags,
    lines: imported.ingredients.length
      ? imported.ingredients.map((line) => ({
          key: newKey(),
          ingredient_id: line.ingredient_id,
          category: line.category,
          name: line.name,
          quantity: line.quantity === null ? '' : String(Number(line.quantity)),
          unit: line.unit,
          note: line.note,
          optional: line.optional,
        }))
      : [emptyLine()],
  }
}

/**
 * Il corpo del form di una ricetta: lo usano "nuova / modifica" e la
 * revisione delle ricette importate. `inferred` sono i campi che l'LLM ha
 * dedotto: hanno il segno "Dedotto" per essere controllati per primi.
 */
export function RecipeEditor({
  draft,
  setDraft,
  errors,
  inferred = [],
  autoFocus,
}: {
  draft: Draft
  setDraft: Dispatch<SetStateAction<Draft>>
  errors: Record<string, string>
  inferred?: string[]
  autoFocus?: boolean
}) {
  const { data: allTags } = useTags()
  const set = (changes: Partial<Draft>) => setDraft((current) => ({ ...current, ...changes }))
  const setLine = (key: string, changes: Partial<LineDraft>) =>
    setDraft((current) => ({
      ...current,
      lines: current.lines.map((line) => (line.key === key ? { ...line, ...changes } : line)),
    }))
  const guess = (field: string) => (inferred.includes(field) ? <Guessed /> : null)

  return (
    <div className="grid gap-4">
      <Card>
        <Field label={gettext('Nome della ricetta')} error={errors.title}>
          <input
            className="field-input"
            value={draft.title}
            maxLength={120}
            onChange={(event) => set({ title: event.target.value })}
            autoFocus={autoFocus}
          />
        </Field>
        <Field
          label={gettext('Descrizione')}
          hint={gettext('Facoltativa: due righe su com’è o da dove viene.')}
        >
          <textarea
            className="field-input min-h-[64px] resize-y"
            value={draft.description}
            maxLength={2000}
            onChange={(event) => set({ description: event.target.value })}
          />
        </Field>
      </Card>

      <Card title={gettext('Porzioni e tempi')} icon="schedule">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="text-body-large">
            {gettext('Porzioni')}
            {guess('servings')}
          </span>
          <Stepper
            label={gettext('Porzioni')}
            value={draft.servings}
            min={1}
            max={50}
            onChange={(servings) => set({ servings })}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field
            label={gettext('Preparazione (min)')}
            error={errors.prep_minutes}
            hint={inferred.includes('prep_minutes') ? gettext('Dedotto') : undefined}
          >
            <input
              className="field-input"
              type="number"
              inputMode="numeric"
              min={0}
              max={1440}
              value={draft.prep_minutes}
              onChange={(event) => set({ prep_minutes: event.target.value })}
            />
          </Field>
          <Field
            label={gettext('Cottura (min)')}
            error={errors.cook_minutes}
            hint={inferred.includes('cook_minutes') ? gettext('Dedotto') : undefined}
          >
            <input
              className="field-input"
              type="number"
              inputMode="numeric"
              min={0}
              max={1440}
              value={draft.cook_minutes}
              onChange={(event) => set({ cook_minutes: event.target.value })}
            />
          </Field>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="text-body-large">
            {gettext('Difficoltà')}
            {guess('difficulty')}
          </span>
          <Segmented
            value={draft.difficulty}
            options={DIFFICULTY_OPTIONS}
            onChange={(difficulty) => set({ difficulty })}
          />
        </div>
      </Card>

      <Card title={gettext('Ingredienti')} icon="grocery">
        <p className="-mt-2 text-body-small text-on-surface-variant">
          {interpolate(
            ngettext(
              'Quantità per %s porzione. Scegli dai suggerimenti per avere allergeni e reparto giusti.',
              'Quantità per %s porzioni. Scegli dai suggerimenti per avere allergeni e reparto giusti.',
              draft.servings,
            ),
            [draft.servings],
          )}
        </p>
        <div className="grid gap-3">
          {draft.lines.map((line, index) => (
            <IngredientRow
              key={line.key}
              line={line}
              index={index}
              onChange={(changes) => setLine(line.key, changes)}
              onRemove={() => set({ lines: draft.lines.filter((other) => other.key !== line.key) })}
            />
          ))}
        </div>
        <button
          type="button"
          className="btn-text w-fit"
          onClick={() => set({ lines: [...draft.lines, emptyLine()] })}
        >
          <Icon name="add" size={20} />
          {gettext('Aggiungi ingrediente')}
        </button>
        {errors.ingredients && <p className="text-body-small text-error">{errors.ingredients}</p>}
      </Card>

      <Card title={gettext('Preparazione')} icon="format_list_numbered">
        <ol className="grid gap-3">
          {draft.steps.map((step, index) => (
            <li key={index} className="flex items-start gap-2">
              <span className="mt-3 flex h-8 w-8 shrink-0 items-center justify-center rounded-pill bg-primary text-body-medium font-medium text-on-primary">
                {index + 1}
              </span>
              <textarea
                className="field min-h-[72px] flex-1 resize-y text-body-large outline-none"
                aria-label={interpolate(gettext('Passo %s'), [index + 1])}
                value={step}
                maxLength={2000}
                onChange={(event) =>
                  set({
                    steps: draft.steps.map((other, at) =>
                      at === index ? event.target.value : other,
                    ),
                  })
                }
              />
              <div className="flex flex-col">
                <IconButton
                  icon="arrow_upward"
                  label={gettext('Sposta su')}
                  disabled={index === 0}
                  onClick={() => set({ steps: move(draft.steps, index, -1) })}
                />
                <IconButton
                  icon="arrow_downward"
                  label={gettext('Sposta giù')}
                  disabled={index === draft.steps.length - 1}
                  onClick={() => set({ steps: move(draft.steps, index, 1) })}
                />
                <IconButton
                  icon="delete"
                  label={gettext('Togli il passo')}
                  disabled={draft.steps.length === 1}
                  onClick={() => set({ steps: draft.steps.filter((_, at) => at !== index) })}
                />
              </div>
            </li>
          ))}
        </ol>
        <button
          type="button"
          className="btn-text w-fit"
          onClick={() => set({ steps: [...draft.steps, ''] })}
        >
          <Icon name="add" size={20} />
          {gettext('Aggiungi un passo')}
        </button>
      </Card>

      <Card title={gettext('Per il piano e il meal prep')} icon="event_note">
        <div>
          <p className="mb-2 text-body-large">
            {gettext('Va bene per')}
            {guess('meal_slots')}
          </p>
          <div className="flex flex-wrap gap-2">
            {MEAL_OPTIONS.map((option) => {
              const active = draft.meal_slots.includes(option.value)
              return (
                <Chip
                  key={option.value}
                  icon={active ? 'check' : option.icon}
                  label={option.label}
                  selected={active}
                  onClick={() =>
                    set({
                      meal_slots: active
                        ? draft.meal_slots.filter((slot) => slot !== option.value)
                        : [...draft.meal_slots, option.value],
                    })
                  }
                />
              )
            })}
          </div>
        </div>
        <div>
          <p className="text-body-large">
            {gettext('Quanto dura in frigo, una volta cucinata?')}
            {guess('keeps_days')}
          </p>
          <p className="mb-2 text-body-small text-on-surface-variant">
            {gettext('Serve per prepararla in anticipo.')}
          </p>
          <div className="flex flex-wrap gap-2">
            {[null, 0, 1, 2, 3, 4, 5].map((days) => (
              <Chip
                key={String(days)}
                label={
                  days === null
                    ? gettext('Non lo so')
                    : days === 0
                      ? gettext('Da mangiare subito')
                      : interpolate(ngettext('%s giorno', '%s giorni', days), [days])
                }
                selected={draft.keeps_days === days}
                onClick={() => set({ keeps_days: days })}
              />
            ))}
          </div>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-body-large">
            {gettext('Si può congelare')}
            {guess('freezable')}
          </span>
          <Switch
            label={gettext('Si può congelare')}
            checked={draft.freezable}
            onChange={(freezable) => set({ freezable })}
          />
        </div>
      </Card>

      <Card title={gettext('Tag')} icon="sell">
        <p className="-mt-2 text-body-small text-on-surface-variant">
          {gettext(
            'Per ritrovarla e per includerla o escluderla dal piano (es. “del cuore”, “veloce”).',
          )}
        </p>
        <ChipEditor
          inputLabel={gettext('Aggiungi un tag')}
          items={draft.tags.map((tag) => ({ key: tag, label: tag }))}
          suggestions={(allTags ?? []).map((tag) => tag.name)}
          onAdd={(tag) => set({ tags: [...draft.tags, tag] })}
          onRemove={(tag) => set({ tags: draft.tags.filter((other) => other !== tag) })}
        />
      </Card>
    </div>
  )
}

/** Il segno accanto a un valore che l'LLM ha dedotto e non letto. */
function Guessed() {
  return (
    <span
      className="ml-2 inline-flex items-center gap-1 rounded-pill bg-tertiary-container px-2 py-0.5 align-middle text-label-small text-on-tertiary-container"
      title={gettext('Il testo non lo diceva: l’ha dedotto l’intelligenza artificiale.')}
    >
      <Icon name="auto_awesome" size={14} />
      {gettext('Dedotto')}
    </span>
  )
}

function move<T>(list: T[], index: number, delta: number): T[] {
  const next = [...list]
  const [item] = next.splice(index, 1)
  next.splice(index + delta, 0, item)
  return next
}

function Card({
  title,
  icon,
  children,
}: {
  title?: string
  icon?: string
  children: React.ReactNode
}) {
  return (
    <section className="grid gap-4 rounded-card bg-surface-container-low p-5">
      {title && (
        <h2 className="flex items-center gap-2 text-title-medium">
          {icon && <Icon name={icon} size={22} className="text-primary" />}
          {title}
        </h2>
      )}
      {children}
    </section>
  )
}

/**
 * Una riga: nome con i suggerimenti del catalogo, quantita', unita', nota.
 * Scegliere un suggerimento collega la riga al catalogo (allergeni e reparto
 * giusti); se si riscrive il nome il collegamento si toglie.
 */
function IngredientRow({
  line,
  index,
  onChange,
  onRemove,
}: {
  line: LineDraft
  index: number
  onChange: (changes: Partial<LineDraft>) => void
  onRemove: () => void
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const box = useRef<HTMLDivElement>(null)
  const quantityInput = useRef<HTMLInputElement>(null)
  useClickOutside(box, open, () => setOpen(false))

  // Si cerca quando si smette di scrivere, e solo per le righe non collegate.
  useEffect(() => {
    if (line.ingredient_id) return
    const timer = window.setTimeout(() => setQuery(line.name), 200)
    return () => window.clearTimeout(timer)
  }, [line.name, line.ingredient_id])
  const { data: suggestions } = useIngredientSearch(open && !line.ingredient_id ? query : '')

  const pick = (ingredient: Ingredient) => {
    onChange({
      ingredient_id: ingredient.id,
      category: ingredient.category,
      name: ingredient.name,
      unit: ingredient.default_unit,
    })
    setOpen(false)
    // Scelto l'ingrediente, si scrive subito la quantita' (il campo c'e' gia').
    quantityInput.current?.focus()
  }

  return (
    <div className="rounded-row bg-surface-container p-3">
      <div className="flex items-start gap-2">
        <div ref={box} className="relative min-w-0 flex-1">
          <label className="field block bg-surface">
            <span className="field-label">
              {interpolate(gettext('Ingrediente %s'), [index + 1])}
            </span>
            <input
              className="field-input"
              value={line.name}
              maxLength={80}
              autoComplete="off"
              onFocus={() => setOpen(true)}
              onChange={(event) => {
                setOpen(true)
                onChange({ name: event.target.value, ingredient_id: null, category: null })
              }}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && suggestions?.length) {
                  event.preventDefault()
                  pick(suggestions[0])
                }
              }}
            />
          </label>
          {open && !line.ingredient_id && suggestions && suggestions.length > 0 && (
            <ul
              role="listbox"
              className="absolute inset-x-0 top-full z-30 mt-1 max-h-64 overflow-y-auto rounded-row bg-surface py-1 shadow-sheet"
            >
              {suggestions.map((ingredient) => (
                <li key={ingredient.id}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={false}
                    className="state flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left"
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => pick(ingredient)}
                  >
                    <span className="text-body-large">{ingredient.name}</span>
                    <span className="text-body-small text-on-surface-variant">
                      {CATEGORY_LABELS[ingredient.category]}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <p
            className={clsx(
              'mt-1 px-1 text-body-small',
              line.ingredient_id ? 'text-on-surface-variant' : 'italic text-on-surface-variant',
            )}
          >
            {line.ingredient_id && line.category
              ? CATEGORY_LABELS[line.category as keyof typeof CATEGORY_LABELS]
              : line.name.trim() && !(open && suggestions?.length)
                ? gettext('Nuovo ingrediente: lo aggiungo al tuo catalogo')
                : ' '}
          </p>
        </div>
        <IconButton
          icon="close"
          label={gettext('Togli l’ingrediente')}
          onClick={onRemove}
          className="mt-2"
        />
      </div>
      <div className="mt-1 grid grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] gap-2 sm:grid-cols-[120px_160px_minmax(0,1fr)]">
        <label className="field block bg-surface">
          <span className="field-label">{gettext('Quantità')}</span>
          <input
            ref={quantityInput}
            className="field-input"
            inputMode="decimal"
            value={line.unit === 'to_taste' ? '' : line.quantity}
            disabled={line.unit === 'to_taste'}
            onChange={(event) => onChange({ quantity: event.target.value.replace(/[^\d.,]/g, '') })}
          />
        </label>
        <label className="field block bg-surface">
          <span className="field-label">{gettext('Unità')}</span>
          <select
            className="field-input"
            value={line.unit}
            onChange={(event) => onChange({ unit: event.target.value as Unit })}
          >
            {UNIT_OPTIONS.map((unit) => (
              <option key={unit} value={unit}>
                {unitLabel(unit, 2)}
              </option>
            ))}
          </select>
        </label>
        <label className="field col-span-2 block bg-surface sm:col-span-1">
          <span className="field-label">{gettext('Nota (es. tritata)')}</span>
          <input
            className="field-input"
            value={line.note}
            maxLength={80}
            onChange={(event) => onChange({ note: event.target.value })}
          />
        </label>
      </div>
      <label className="mt-2 inline-flex cursor-pointer items-center gap-2 px-1 text-body-medium text-on-surface-variant">
        <input
          type="checkbox"
          className="h-4 w-4 accent-[var(--primary)]"
          checked={line.optional}
          onChange={(event) => onChange({ optional: event.target.checked })}
        />
        {gettext('Facoltativo')}
      </label>
    </div>
  )
}
