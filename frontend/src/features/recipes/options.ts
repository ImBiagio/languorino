// Etichette e formati del ricettario: unita' al singolare e plurale,
// quantita' leggibili ("1,5 kg", "2 spicchi"), tempi, difficolta', reparti.

import { gettext, intlLocale, ngettext } from '../../lib/i18n'
import type { Category, Difficulty, Unit } from '../../lib/types'

export const DIFFICULTY_OPTIONS: { value: Difficulty; label: string }[] = [
  { value: 'easy', label: gettext('Facile') },
  { value: 'medium', label: gettext('Media') },
  { value: 'hard', label: gettext('Difficile') },
]

export function difficultyLabel(value: Difficulty): string {
  return DIFFICULTY_OPTIONS.find((option) => option.value === value)?.label ?? value
}

/** Etichette dei valori nutrizionali (ADR 0018), con l'unita'. */
export function nutritionLabel(field: 'kcal' | 'protein_g' | 'carbs_g' | 'fat_g'): string {
  return {
    kcal: gettext('Calorie (kcal)'),
    protein_g: gettext('Proteine (g)'),
    carbs_g: gettext('Carboidrati (g)'),
    fat_g: gettext('Grassi (g)'),
  }[field]
}

export const CATEGORY_LABELS: Record<Category, string> = {
  produce: gettext('Frutta e verdura'),
  meat: gettext('Carne e salumi'),
  fish: gettext('Pesce'),
  dairy: gettext('Latticini e uova'),
  bakery: gettext('Pane e forno'),
  pantry: gettext('Dispensa'),
  spices: gettext('Spezie e condimenti'),
  frozen: gettext('Surgelati'),
  drinks: gettext('Bevande'),
  other: gettext('Altro'),
}

/** Le unita' nel menu del form, nell'ordine in cui servono piu' spesso. */
export const UNIT_OPTIONS: Unit[] = [
  'g',
  'kg',
  'ml',
  'l',
  'pz',
  'tbsp',
  'tsp',
  'clove',
  'slice',
  'pinch',
  'bunch',
  'cup',
  'can',
  'to_taste',
]

/** L'unita' accordata alla quantita': "1 spicchio", "3 spicchi". */
export function unitLabel(unit: Unit, quantity = 1): string {
  switch (unit) {
    case 'pz':
      return gettext('pz')
    case 'tbsp':
      return ngettext('cucchiaio', 'cucchiai', quantity)
    case 'tsp':
      return ngettext('cucchiaino', 'cucchiaini', quantity)
    case 'cup':
      return ngettext('tazza', 'tazze', quantity)
    case 'pinch':
      return ngettext('pizzico', 'pizzichi', quantity)
    case 'clove':
      return ngettext('spicchio', 'spicchi', quantity)
    case 'slice':
      return ngettext('fetta', 'fette', quantity)
    case 'bunch':
      return ngettext('mazzetto', 'mazzetti', quantity)
    case 'can':
      return ngettext('scatola', 'scatole', quantity)
    case 'to_taste':
      return gettext('q.b.')
    default:
      return unit
  }
}

/**
 * "180 g", "1,5 kg", "2 spicchi", "q.b.": la quantita' moltiplicata per
 * `factor` (porzioni scelte / porzioni della ricetta). I grammi sopra 10 si
 * arrotondano all'unita': "183,33 g" non serve a nessuno.
 */
export function formatQuantity(quantity: string | null, unit: Unit, factor = 1): string {
  if (unit === 'to_taste') return gettext('q.b.')
  if (quantity === null) return ''
  const value = Number(quantity) * factor
  const fine = ['g', 'ml'].includes(unit) && value >= 10
  const number = new Intl.NumberFormat(intlLocale(), {
    maximumFractionDigits: fine ? 0 : value < 10 ? 2 : 1,
  }).format(value)
  return `${number} ${unitLabel(unit, value)}`
}

/** "45 min", "1 h 20 min". */
export function formatMinutes(minutes: number): string {
  if (minutes < 60) return `${minutes} min`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return rest ? `${hours} h ${rest} min` : `${hours} h`
}
