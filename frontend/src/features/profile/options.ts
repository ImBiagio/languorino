// Etichette delle scelte del profilo. I valori sono quelli del backend
// (`profiles/models.py`); le etichette passano da gettext al caricamento del
// modulo, dopo il catalogo (main.tsx).

import { gettext } from '../../lib/i18n'
import type { ActivityLevel, Allergen, FoodPreference, Goal, MealSlot, Sex } from '../../lib/types'

export const SEX_OPTIONS: { value: Sex; label: string }[] = [
  { value: 'f', label: gettext('Donna') },
  { value: 'm', label: gettext('Uomo') },
  { value: 'other', label: gettext('Preferisco non dirlo') },
]

export const GOAL_OPTIONS: { value: Goal; label: string; icon: string }[] = [
  { value: 'lose_weight', label: gettext('Perdere peso'), icon: 'trending_down' },
  { value: 'gain_muscle', label: gettext('Aumentare la massa muscolare'), icon: 'fitness_center' },
  { value: 'maintain', label: gettext('Mantenere il peso'), icon: 'balance' },
  { value: 'more_protein', label: gettext('Mangiare più proteine'), icon: 'egg' },
  { value: 'eat_better', label: gettext('Mangiare più sano'), icon: 'nutrition' },
  { value: 'more_variety', label: gettext('Mangiare più vario'), icon: 'shuffle' },
  { value: 'save_time', label: gettext('Perdere meno tempo in cucina'), icon: 'timer' },
  { value: 'save_money', label: gettext('Spendere meno'), icon: 'savings' },
]

export const ACTIVITY_OPTIONS: { value: ActivityLevel; label: string; hint: string }[] = [
  {
    value: 'sedentary',
    label: gettext('Sedentario'),
    hint: gettext('Lavoro seduto, poco movimento'),
  },
  {
    value: 'light',
    label: gettext('Leggero'),
    hint: gettext('Cammino un po’ ogni giorno'),
  },
  {
    value: 'moderate',
    label: gettext('Moderato'),
    hint: gettext('In piedi tanto, o sport qualche volta'),
  },
  {
    value: 'intense',
    label: gettext('Intenso'),
    hint: gettext('Lavoro fisico o sport quasi ogni giorno'),
  },
]

export const MEAL_OPTIONS: { value: MealSlot; label: string; icon: string }[] = [
  { value: 'breakfast', label: gettext('Colazione'), icon: 'coffee' },
  { value: 'morning_snack', label: gettext('Spuntino di metà mattina'), icon: 'nutrition' },
  { value: 'lunch', label: gettext('Pranzo'), icon: 'lunch_dining' },
  { value: 'afternoon_snack', label: gettext('Merenda'), icon: 'bakery_dining' },
  { value: 'dinner', label: gettext('Cena'), icon: 'dinner_dining' },
]

export const ALLERGEN_OPTIONS: { value: Allergen; label: string }[] = [
  { value: 'gluten', label: gettext('Glutine') },
  { value: 'milk', label: gettext('Latte e lattosio') },
  { value: 'eggs', label: gettext('Uova') },
  { value: 'nuts', label: gettext('Frutta a guscio') },
  { value: 'peanuts', label: gettext('Arachidi') },
  { value: 'fish', label: gettext('Pesce') },
  { value: 'crustaceans', label: gettext('Crostacei') },
  { value: 'molluscs', label: gettext('Molluschi') },
  { value: 'soy', label: gettext('Soia') },
  { value: 'sesame', label: gettext('Sesamo') },
  { value: 'celery', label: gettext('Sedano') },
  { value: 'mustard', label: gettext('Senape') },
  { value: 'sulphites', label: gettext('Solfiti') },
  { value: 'lupin', label: gettext('Lupini') },
]

/** Spunti per i campi liberi: si toccano per aggiungerli. */
export const INTOLERANCE_SUGGESTIONS = [
  gettext('Lattosio'),
  gettext('Glutine'),
  gettext('Nichel'),
  gettext('Fruttosio'),
  gettext('Istamina'),
]

export const CONDITION_SUGGESTIONS = [
  gettext('Diabete'),
  gettext('Ipertensione'),
  gettext('Colesterolo alto'),
  gettext('Reflusso'),
  gettext('Colon irritabile'),
  gettext('Ipotiroidismo'),
]

export const DISLIKE_SUGGESTIONS = [
  gettext('Funghi'),
  gettext('Peperoni'),
  gettext('Cipolla'),
  gettext('Aglio'),
  gettext('Coriandolo'),
  gettext('Pesce'),
  gettext('Legumi'),
  gettext('Melanzane'),
  gettext('Olive'),
  gettext('Piccante'),
]

export const LIKE_SUGGESTIONS = [
  gettext('Pasta'),
  gettext('Riso'),
  gettext('Pollo'),
  gettext('Pesce'),
  gettext('Legumi'),
  gettext('Verdure al forno'),
  gettext('Zuppe'),
  gettext('Uova'),
  gettext('Formaggi'),
  gettext('Dolci'),
]

/**
 * Un'allergia scelta dai chip dei 14 allergeni: l'etichetta salvata e' il
 * codice stesso ("nuts"), cosi' resta riconoscibile in ogni lingua.
 */
export function isAllergenChip(item: FoodPreference): boolean {
  return Boolean(item.allergen) && item.label === item.allergen
}

/** L'etichetta da mostrare: i chip degli allergeni si traducono, il resto e' testo. */
export function preferenceLabel(item: FoodPreference): string {
  if (!isAllergenChip(item)) return item.label
  return ALLERGEN_OPTIONS.find((option) => option.value === item.allergen)?.label ?? item.label
}
