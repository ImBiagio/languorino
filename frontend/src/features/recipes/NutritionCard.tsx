// Calorie e macro della ricetta (ADR 0018): a porzione e per le porzioni
// scelte; scritti nella ricetta, a mano o stimati dall'AI dagli ingredienti.

import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import { keys, useEstimateNutrition, useJob } from '../../api/hooks'
import { ErrorBanner, Icon } from '../../components/ui'
import { gettext, interpolate, ngettext } from '../../lib/i18n'
import type { Nutrition, Recipe } from '../../lib/types'

const MACROS = [
  { field: 'protein_g', label: () => gettext('Proteine'), color: 'bg-primary' },
  { field: 'carbs_g', label: () => gettext('Carboidrati'), color: 'bg-accent' },
  { field: 'fat_g', label: () => gettext('Grassi'), color: 'bg-success' },
] as const

function sourceLabel(source: Nutrition['nutrition_source']): string {
  switch (source) {
    case 'recipe':
      return gettext('Dalla ricetta')
    case 'ai':
      return gettext('Stima dell’AI dagli ingredienti')
    case 'manual':
      return gettext('Scritti a mano')
    default:
      return ''
  }
}

function amount(value: number, decimals = 0): string {
  return value.toLocaleString(undefined, { maximumFractionDigits: decimals })
}

/** Solo lettura: dettaglio e pagina pubblica. ``servings`` le porzioni scelte. */
export function NutritionFacts({
  nutrition,
  servings,
}: {
  nutrition: Nutrition
  servings: number
}) {
  const grams = MACROS.map((macro) => Number(nutrition[macro.field] ?? 0))
  // Energia da ciascun macro (4/4/9 kcal per grammo): per la barra delle proporzioni.
  const energy = [grams[0] * 4, grams[1] * 4, grams[2] * 9]
  const total = energy.reduce((sum, value) => sum + value, 0)

  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="amount text-[28px] font-medium leading-9">
          {nutrition.kcal === null ? '–' : amount(nutrition.kcal)}
        </span>
        <span className="text-body-medium text-on-surface-variant">
          {gettext('kcal a porzione')}
        </span>
        {servings > 1 && nutrition.kcal !== null && (
          <span className="text-body-medium text-on-surface-variant">
            {interpolate(
              ngettext('· %s kcal per %s porzione', '· %s kcal per %s porzioni', servings),
              [amount(nutrition.kcal * servings), servings],
            )}
          </span>
        )}
      </div>
      {total > 0 && (
        <div
          className="flex h-2 overflow-hidden rounded-pill bg-surface-container-high"
          aria-hidden
        >
          {MACROS.map((macro, index) => (
            <span
              key={macro.field}
              className={macro.color}
              style={{ width: `${(energy[index] / total) * 100}%` }}
            />
          ))}
        </div>
      )}
      <dl className="grid grid-cols-3 gap-2">
        {MACROS.map((macro, index) => (
          <div key={macro.field} className="rounded-row bg-surface-container px-3 py-2">
            <dt className="flex items-center gap-1.5 text-body-small text-on-surface-variant">
              <span className={`h-2 w-2 rounded-pill ${macro.color}`} />
              {macro.label()}
            </dt>
            <dd className="amount text-body-large font-medium">
              {nutrition[macro.field] === null ? '–' : `${amount(grams[index], 1)} g`}
            </dd>
            {servings > 1 && nutrition[macro.field] !== null && (
              <dd className="amount text-body-small text-on-surface-variant">
                {interpolate(gettext('%s g in tutto'), [amount(grams[index] * servings, 1)])}
              </dd>
            )}
          </div>
        ))}
      </dl>
      {nutrition.nutrition_source && (
        <p className="text-body-small text-on-surface-variant">
          {sourceLabel(nutrition.nutrition_source)}
          {nutrition.nutrition_source === 'ai' && ` · ${gettext('valori indicativi')}`}
        </p>
      )}
    </div>
  )
}

/** Nel dettaglio della propria ricetta: valori, stima e ricalcolo. */
export function NutritionCard({ recipe, servings }: { recipe: Recipe; servings: number }) {
  const client = useQueryClient()
  const start = useEstimateNutrition()
  const [jobId, setJobId] = useState<string>()
  const [open, setOpen] = useState(false)
  const { data: job } = useJob(jobId)
  const working = start.isPending || job?.status === 'queued' || job?.status === 'running'
  const has = recipe.kcal !== null || recipe.protein_g !== null

  useEffect(() => {
    if (job?.status === 'ready') {
      void client.invalidateQueries({ queryKey: keys.recipe(recipe.id) })
    }
  }, [job?.status, client, recipe.id])

  const run = async () => {
    try {
      const created = await start.mutateAsync(recipe.id)
      setJobId(created.id)
    } catch {
      // Errore sotto.
    }
  }
  const detail = 'ingredients' in recipe.nutrition_detail ? recipe.nutrition_detail : null

  return (
    <section className="grid gap-3 rounded-card bg-surface-container-low p-5">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-title-medium">{gettext('Calorie e macro')}</h2>
        {has && recipe.ingredients.length > 0 && (
          <button type="button" className="btn-text btn-sm" disabled={working} onClick={run}>
            <Icon name="autorenew" size={18} />
            {working ? gettext('Calcolo…') : gettext('Ricalcola con l’AI')}
          </button>
        )}
      </header>
      {has ? (
        <NutritionFacts nutrition={recipe} servings={servings} />
      ) : (
        <div className="grid gap-3">
          <p className="text-body-medium text-on-surface-variant">
            {recipe.ingredients.length
              ? gettext(
                  'La ricetta non li dice. L’AI li stima dagli ingredienti e dalle quantità; puoi anche scriverli a mano modificando la ricetta.',
                )
              : gettext('Aggiungi gli ingredienti per poterli stimare.')}
          </p>
          {recipe.ingredients.length > 0 && (
            <button type="button" className="btn-filled w-fit" disabled={working} onClick={run}>
              <Icon name="calculate" size={20} />
              {working ? gettext('Calcolo…') : gettext('Calcola calorie e macro')}
            </button>
          )}
        </div>
      )}
      {detail && (
        <div>
          <button
            type="button"
            className="btn-text btn-sm -ml-3"
            aria-expanded={open}
            onClick={() => setOpen(!open)}
          >
            <Icon name={open ? 'expand_less' : 'expand_more'} size={18} />
            {gettext('Come li ho stimati')}
          </button>
          {open && (
            <div className="mt-2 grid gap-2">
              <table className="w-full text-body-small">
                <thead className="text-on-surface-variant">
                  <tr>
                    <th className="py-1 text-left font-normal">
                      {interpolate(
                        ngettext(
                          'Ingrediente (per %s porzione)',
                          'Ingrediente (per %s porzioni)',
                          detail.servings,
                        ),
                        [detail.servings],
                      )}
                    </th>
                    <th className="py-1 text-right font-normal">g</th>
                    <th className="py-1 text-right font-normal">kcal</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-outline-variant">
                  {detail.ingredients.map((item, index) => (
                    <tr key={index}>
                      <td className="py-1.5">{item.name}</td>
                      <td className="amount py-1.5 text-right">{amount(item.grams)}</td>
                      <td className="amount py-1.5 text-right">{amount(item.kcal)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {detail.note && (
                <p className="text-body-small text-on-surface-variant">{detail.note}</p>
              )}
            </div>
          )}
        </div>
      )}
      {job?.status === 'failed' && (
        <p className="text-body-medium text-error">
          {job.error || gettext('Non sono riuscito a stimarli. Riprova.')}
        </p>
      )}
      <ErrorBanner error={start.error} />
    </section>
  )
}
