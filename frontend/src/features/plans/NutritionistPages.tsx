// Piano del nutrizionista (ADR 0010): si carica il PDF o le foto, l'LLM ne
// ricava le regole (opzioni per pasto con grammature, frequenze, alimenti
// liberi e da evitare), l'utente le rivede e conferma; poi si generano i piani
// da li'.

import clsx from 'clsx'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import {
  useConfirmNutritionistPlan,
  useDeleteNutritionistPlan,
  useJob,
  useNutritionistPlan,
  useNutritionistPlans,
  useReadNutritionistPlan,
  useUpdateNutritionistPlan,
} from '../../api/hooks'
import { useConfirm } from '../../components/ConfirmDialog'
import { Page } from '../../components/Layout'
import { FoodPattern } from '../../components/illustrations'
import {
  Chip,
  ChipEditor,
  ErrorBanner,
  Field,
  Icon,
  IconButton,
  Skeleton,
  Stepper,
  Switch,
} from '../../components/ui'
import { ApiError } from '../../lib/api'
import { gettext, interpolate, ngettext } from '../../lib/i18n'
import type { MealSlot, NutritionistPlan, NutritionistRules } from '../../lib/types'
import { MEAL_OPTIONS } from '../profile/options'
import { FileThumb } from '../recipes/ImportPages'
import { formatDayLong } from './dates'

const MAX_FILES = 8

function slotLabel(slot: MealSlot): string {
  return MEAL_OPTIONS.find((option) => option.value === slot)?.label ?? slot
}

function validity(plan: NutritionistPlan): string {
  if (plan.valid_from && plan.valid_to) {
    return interpolate(gettext('Dal %s al %s'), [
      formatDayLong(plan.valid_from).toLowerCase(),
      formatDayLong(plan.valid_to).toLowerCase(),
    ])
  }
  if (plan.valid_from) {
    return interpolate(gettext('Dal %s'), [formatDayLong(plan.valid_from).toLowerCase()])
  }
  return ''
}

/* ---------------------------------------------- /piano/nutrizionista ---- */

export function NutritionistHomePage() {
  const navigate = useNavigate()
  const { data: plans } = useNutritionistPlans()
  const read = useReadNutritionistPlan()
  const [files, setFiles] = useState<File[]>([])
  const [jobId, setJobId] = useState<string>()
  const { data: job } = useJob(jobId)
  const input = useRef<HTMLInputElement>(null)
  const reading = read.isPending || job?.status === 'queued' || job?.status === 'running'

  // Letto: si apre la bozza da rivedere.
  useEffect(() => {
    if (job?.status === 'ready' && job.result.nutritionist_plan) {
      navigate(`/piano/nutrizionista/${job.result.nutritionist_plan}`, { replace: true })
    }
  }, [job, navigate])

  return (
    <Page className="px-5 pb-8 pt-5 md:px-8 md:pt-8">
      <header className="mb-5 flex items-center gap-3">
        <IconButton
          icon="arrow_back"
          size="md"
          label={gettext('Piano')}
          onClick={() => navigate('/piano')}
        />
        <h1 className="flex-1 text-title-large">{gettext('Piano del nutrizionista')}</h1>
      </header>

      <div className="grid gap-4">
        <section className="relative overflow-hidden rounded-panel bg-primary px-6 py-6 text-on-primary">
          <FoodPattern tone="dark" opacity={0.3} />
          <p className="relative max-w-xl text-body-large">
            {gettext(
              'Carica il piano che ti ha dato il nutrizionista: leggo le opzioni di ogni pasto con le grammature, tu controlli e poi compongo le settimane seguendolo.',
            )}
          </p>
        </section>

        {plans && plans.length > 0 && (
          <section className="grid gap-2">
            {plans.map((plan) => (
              <Link
                key={plan.id}
                to={`/piano/nutrizionista/${plan.id}`}
                className="state flex items-center gap-4 rounded-card bg-surface-container-low p-4"
              >
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[14px] bg-primary-container text-on-primary-container">
                  <Icon name="clinical_notes" size={24} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-body-large font-medium">{plan.title}</span>
                  <span className="block text-body-small text-on-surface-variant">
                    {[
                      plan.status === 'draft' ? gettext('Da rivedere') : gettext('Confermato'),
                      interpolate(ngettext('%s pasto', '%s pasti', plan.rules.meals.length), [
                        plan.rules.meals.length,
                      ]),
                      validity(plan),
                    ]
                      .filter(Boolean)
                      .join(' · ')}
                  </span>
                </span>
                <Icon name="chevron_right" size={22} />
              </Link>
            ))}
          </section>
        )}

        <section className="grid gap-4 rounded-card bg-surface-container-low p-5">
          <h2 className="flex items-center gap-2 text-title-medium">
            <Icon name="upload_file" size={22} className="text-primary" />
            {plans?.length ? gettext('Carica un piano nuovo') : gettext('Carica il piano')}
          </h2>
          <input
            ref={input}
            type="file"
            accept="application/pdf,image/jpeg,image/png,image/webp,image/heic,image/heif"
            multiple
            hidden
            onChange={(event) => {
              const list = Array.from(event.target.files ?? [])
              event.target.value = ''
              setFiles((current) => [...current, ...list].slice(0, MAX_FILES))
            }}
          />
          <button
            type="button"
            className="state flex items-center gap-4 rounded-row bg-primary-container p-4 text-left text-on-primary-container"
            onClick={() => input.current?.click()}
            disabled={reading}
          >
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[14px] bg-primary text-on-primary">
              <Icon name="add_photo_alternate" size={24} />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-body-large font-medium">
                {gettext('Scegli il PDF o le foto')}
              </span>
              <span className="block text-body-small opacity-80">
                {interpolate(gettext('Fino a %s file: tutte le pagine del piano.'), [MAX_FILES])}
              </span>
            </span>
          </button>
          {files.length > 0 && (
            <ul className="grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-6">
              {files.map((file, index) => (
                <FileThumb
                  key={`${file.name}-${index}`}
                  file={file}
                  onRemove={() => setFiles(files.filter((_, at) => at !== index))}
                />
              ))}
            </ul>
          )}
          {reading && (
            <p className="flex items-center gap-2 text-body-medium text-on-surface-variant">
              <Icon name="hourglass_top" size={20} className="animate-pulse" />
              {gettext('Leggo il piano: può volerci un minuto…')}
            </p>
          )}
          {job?.status === 'ready' && job.result.problem && (
            <p className="rounded-row bg-warning-container px-4 py-3 text-body-medium text-on-warning-container">
              {job.result.problem}
            </p>
          )}
          {job?.status === 'failed' && <ErrorBanner error={job.error} />}
          <ErrorBanner error={read.error} />
          <button
            type="button"
            className="btn-filled justify-self-end"
            disabled={!files.length || reading}
            onClick={async () => {
              try {
                const created = await read.mutateAsync(files)
                setJobId(created.id)
                setFiles([])
              } catch {
                // Errore sopra.
              }
            }}
          >
            <Icon name="auto_awesome" size={20} />
            {gettext('Leggi il piano')}
          </button>
        </section>

        <p className="flex items-start gap-2 px-1 text-body-small text-on-surface-variant">
          <Icon name="info" size={18} />
          {gettext(
            'Languorino non sostituisce il nutrizionista: segue le sue indicazioni, ma per dubbi su dosi e salute chiedi a lui.',
          )}
        </p>
      </div>
    </Page>
  )
}

/* ----------------------------------------- /piano/nutrizionista/:id ---- */

export function NutritionistPlanPage() {
  const { planId } = useParams()
  const { data: plan, error } = useNutritionistPlan(planId)
  if (error) {
    return (
      <Page className="px-5 pt-5 md:px-8 md:pt-8">
        <ErrorBanner error={error} />
      </Page>
    )
  }
  if (!plan) return <Skeleton className="m-5 h-72 rounded-card md:m-8" />
  // La chiave riparte dalla versione salvata quando cambia il piano.
  return <NutritionistEditor key={`${plan.id}-${plan.updated_at}`} plan={plan} />
}

function NutritionistEditor({ plan }: { plan: NutritionistPlan }) {
  const navigate = useNavigate()
  const confirm = useConfirm()
  const update = useUpdateNutritionistPlan()
  const confirmPlan = useConfirmNutritionistPlan()
  const remove = useDeleteNutritionistPlan()
  const [title, setTitle] = useState(plan.title)
  const [strict, setStrict] = useState(plan.strict)
  const [validFrom, setValidFrom] = useState(plan.valid_from ?? '')
  const [validTo, setValidTo] = useState(plan.valid_to ?? '')
  const [rules, setRules] = useState<NutritionistRules>(plan.rules)
  const errors = update.error instanceof ApiError ? update.error.fieldErrors() : {}
  const draft = plan.status === 'draft'
  const busy = update.isPending || confirmPlan.isPending
  const setRule = (changes: Partial<NutritionistRules>) =>
    setRules((current) => ({ ...current, ...changes }))
  const missing = MEAL_OPTIONS.filter(
    (option) => !rules.meals.some((meal) => meal.slot === option.value),
  )

  const setOptions = (slot: MealSlot, options: string[]) =>
    setRule({
      meals: rules.meals.map((meal) => (meal.slot === slot ? { ...meal, options } : meal)),
    })

  const save = () =>
    update.mutateAsync({
      id: plan.id,
      title,
      strict,
      valid_from: validFrom || null,
      valid_to: validTo || null,
      rules: {
        ...rules,
        meals: rules.meals.map((meal) => ({
          ...meal,
          options: meal.options.map((option) => option.trim()).filter(Boolean),
        })),
        weekly: rules.weekly.filter((item) => item.food.trim()),
      },
    })

  return (
    <Page className="px-5 pb-8 pt-5 md:px-8 md:pt-8">
      <header className="mb-5 flex items-center gap-3">
        <IconButton
          icon="arrow_back"
          size="md"
          label={gettext('Piano del nutrizionista')}
          onClick={() => navigate('/piano/nutrizionista')}
        />
        <h1 className="min-w-0 flex-1 truncate text-title-large">{plan.title}</h1>
        <IconButton
          icon="delete"
          size="md"
          label={gettext('Elimina')}
          onClick={async () => {
            const ok = await confirm({
              title: gettext('Eliminare il piano del nutrizionista?'),
              message: gettext('Spariscono anche i file caricati. I piani già generati restano.'),
              confirmLabel: gettext('Elimina'),
              icon: 'delete',
              destructive: true,
            })
            if (!ok) return
            await remove.mutateAsync(plan.id)
            navigate('/piano/nutrizionista', { replace: true })
          }}
        />
      </header>

      <div className="grid gap-4">
        {draft ? (
          <section className="flex items-start gap-3 rounded-row bg-tertiary-container px-4 py-3 text-on-tertiary-container">
            <Icon name="auto_awesome" size={22} />
            <p className="text-body-medium">
              {gettext(
                'Letto automaticamente: controlla opzioni e grammature con il piano originale, correggi e conferma.',
              )}
            </p>
          </section>
        ) : (
          <section className="flex flex-wrap items-center gap-3 rounded-row bg-success-container px-4 py-3 text-on-success-container">
            <Icon name="verified" size={22} />
            <p className="min-w-0 flex-1 text-body-medium">
              {gettext('Confermato: puoi generare piani che lo seguono.')}
            </p>
            <Link to={`/piano/nuovo?nutrizionista=${plan.id}`} className="btn-filled btn-sm">
              <Icon name="auto_awesome" size={18} />
              {gettext('Crea un piano da qui')}
            </Link>
          </section>
        )}

        <Card title={gettext('In generale')} icon="clinical_notes">
          <Field label={gettext('Nome')} error={errors.title}>
            <input
              className="field-input"
              value={title}
              maxLength={120}
              onChange={(event) => setTitle(event.target.value)}
            />
          </Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={gettext('Valido dal')} error={errors.valid_from}>
              <input
                className="field-input"
                type="date"
                value={validFrom}
                onChange={(event) => setValidFrom(event.target.value)}
              />
            </Field>
            <Field label={gettext('Fino al')} error={errors.valid_to}>
              <input
                className="field-input"
                type="date"
                value={validTo}
                onChange={(event) => setValidTo(event.target.value)}
              />
            </Field>
          </div>
          <div className="flex items-start justify-between gap-4">
            <span>
              <span className="block text-body-large">{gettext('Seguilo alla lettera')}</span>
              <span className="block text-body-small text-on-surface-variant">
                {strict
                  ? gettext('Ogni pasto è una delle opzioni del nutrizionista.')
                  : gettext(
                      'Anche piatti equivalenti, con le stesse grammature e frequenze: più varietà.',
                    )}
              </span>
            </span>
            <Switch label={gettext('Seguilo alla lettera')} checked={strict} onChange={setStrict} />
          </div>
          {plan.files.length > 0 && (
            <p className="flex flex-wrap items-center gap-1.5 text-body-small text-on-surface-variant">
              <Icon name="attach_file" size={16} />
              {plan.files.map((file) => file.original_name).join(', ')}
            </p>
          )}
        </Card>

        <Card title={gettext('Pasti')} icon="restaurant">
          {rules.meals.map((meal) => (
            <div key={meal.slot} className="grid gap-2">
              <div className="flex items-center gap-2">
                <h3 className="flex-1 text-body-large font-medium">{slotLabel(meal.slot)}</h3>
                <IconButton
                  icon="delete"
                  label={interpolate(gettext('Togli %s'), [slotLabel(meal.slot).toLowerCase()])}
                  onClick={() =>
                    setRule({ meals: rules.meals.filter((other) => other.slot !== meal.slot) })
                  }
                />
              </div>
              {meal.options.map((option, index) => (
                <div key={index} className="flex items-start gap-2">
                  <span className="mt-4 w-5 shrink-0 text-center text-label-large text-on-surface-variant">
                    {index + 1}
                  </span>
                  <Field
                    label={interpolate(gettext('Opzione %s'), [index + 1])}
                    className="min-w-0 flex-1"
                  >
                    <textarea
                      className="field-input min-h-[56px] resize-y"
                      maxLength={300}
                      value={option}
                      onChange={(event) =>
                        setOptions(
                          meal.slot,
                          meal.options.map((other, at) =>
                            at === index ? event.target.value : other,
                          ),
                        )
                      }
                    />
                  </Field>
                  <IconButton
                    icon="close"
                    label={gettext('Togli l’opzione')}
                    className="mt-2"
                    onClick={() =>
                      setOptions(
                        meal.slot,
                        meal.options.filter((_, at) => at !== index),
                      )
                    }
                  />
                </div>
              ))}
              <button
                type="button"
                className="btn-text btn-sm justify-self-start"
                onClick={() => setOptions(meal.slot, [...meal.options, ''])}
              >
                <Icon name="add" size={18} />
                {gettext('Aggiungi un’opzione')}
              </button>
            </div>
          ))}
          {missing.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {missing.map((option) => (
                <Chip
                  key={option.value}
                  icon="add"
                  label={option.label}
                  onClick={() => {
                    const order = MEAL_OPTIONS.map((item) => item.value)
                    setRule({
                      meals: [...rules.meals, { slot: option.value, options: [''] }].sort(
                        (a, b) => order.indexOf(a.slot) - order.indexOf(b.slot),
                      ),
                    })
                  }}
                />
              ))}
            </div>
          )}
          {errors.rules && <p className="text-body-small text-error">{errors.rules}</p>}
        </Card>

        <Card title={gettext('Quante volte a settimana')} icon="event_repeat">
          {rules.weekly.map((item, index) => (
            <div key={index} className="flex flex-wrap items-center gap-3">
              <Field label={gettext('Alimento')} className="min-w-[10rem] flex-1">
                <input
                  className="field-input"
                  value={item.food}
                  maxLength={80}
                  onChange={(event) =>
                    setRule({
                      weekly: rules.weekly.map((other, at) =>
                        at === index ? { ...other, food: event.target.value } : other,
                      ),
                    })
                  }
                />
              </Field>
              <Stepper
                label={gettext('Volte a settimana')}
                value={item.times}
                min={1}
                max={21}
                onChange={(times) =>
                  setRule({
                    weekly: rules.weekly.map((other, at) =>
                      at === index ? { ...other, times } : other,
                    ),
                  })
                }
              />
              <IconButton
                icon="close"
                label={gettext('Togli')}
                onClick={() => setRule({ weekly: rules.weekly.filter((_, at) => at !== index) })}
              />
            </div>
          ))}
          <button
            type="button"
            className="btn-text btn-sm justify-self-start"
            onClick={() => setRule({ weekly: [...rules.weekly, { food: '', times: 2 }] })}
          >
            <Icon name="add" size={18} />
            {gettext('Aggiungi una frequenza')}
          </button>
        </Card>

        <Card title={gettext('Alimenti')} icon="nutrition">
          <div>
            <p className="mb-2 text-body-large">{gettext('Liberi')}</p>
            <ChipEditor
              inputLabel={gettext('Alimento libero')}
              items={rules.free_foods.map((food) => ({ key: food, label: food }))}
              onAdd={(food) => setRule({ free_foods: [...rules.free_foods, food] })}
              onRemove={(food) =>
                setRule({ free_foods: rules.free_foods.filter((other) => other !== food) })
              }
            />
          </div>
          <div>
            <p className="mb-1 text-body-large">{gettext('Da evitare')}</p>
            <p className="mb-2 text-body-small text-on-surface-variant">
              {gettext('Non entrano mai nel piano, come le allergie.')}
            </p>
            <ChipEditor
              inputLabel={gettext('Alimento da evitare')}
              items={rules.avoid_foods.map((food) => ({ key: food, label: food }))}
              onAdd={(food) => setRule({ avoid_foods: [...rules.avoid_foods, food] })}
              onRemove={(food) =>
                setRule({ avoid_foods: rules.avoid_foods.filter((other) => other !== food) })
              }
            />
          </div>
          <Field label={gettext('Altre indicazioni')}>
            <textarea
              className="field-input min-h-[72px] resize-y"
              maxLength={1000}
              value={rules.notes}
              onChange={(event) => setRule({ notes: event.target.value })}
            />
          </Field>
        </Card>

        <ErrorBanner error={update.error ?? confirmPlan.error ?? remove.error} />
        <div className="flex flex-wrap justify-end gap-2">
          <button
            type="button"
            className={clsx(draft ? 'btn-text' : 'btn-filled')}
            disabled={busy}
            onClick={async () => {
              try {
                await save()
              } catch {
                // Errori sui campi.
              }
            }}
          >
            <Icon name="save" size={20} />
            {gettext('Salva')}
          </button>
          {draft && (
            <button
              type="button"
              className="btn-filled"
              disabled={busy || !rules.meals.length}
              onClick={async () => {
                try {
                  await save()
                  await confirmPlan.mutateAsync(plan.id)
                } catch {
                  // Errori sui campi o in fondo.
                }
              }}
            >
              <Icon name="check" size={20} />
              {gettext('Conferma il piano')}
            </button>
          )}
        </div>
      </div>
    </Page>
  )
}

function Card({
  title,
  icon,
  children,
}: {
  title: string
  icon: string
  children: React.ReactNode
}) {
  return (
    <section className="grid gap-4 rounded-card bg-surface-container-low p-5">
      <h2 className="flex items-center gap-2 text-title-medium">
        <Icon name={icon} size={22} className="text-primary" />
        {title}
      </h2>
      {children}
    </section>
  )
}
