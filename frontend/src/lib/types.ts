// Tipi allineati agli serializer DRF (`npm run api:generate` produce il client
// tipizzato completo da OpenAPI, se un giorno servira').

export type UUID = string
export type Money = string // Decimal serializzato: mai un number, mai float.

export interface User {
  id: UUID
  email: string
  display_name: string
  avatar: string | null
  email_verified_at?: string | null
  /** Lingua dell'interfaccia e delle mail ('it' | 'en'). */
  language?: string
}

/* ------------------------------------------------------ profilo alimentare -- */

export type Sex = 'f' | 'm' | 'other'
export type Goal =
  | 'lose_weight'
  | 'gain_muscle'
  | 'maintain'
  | 'more_protein'
  | 'eat_better'
  | 'more_variety'
  | 'save_time'
  | 'save_money'
export type ActivityLevel = 'sedentary' | 'light' | 'moderate' | 'intense'
export type MealSlot = 'breakfast' | 'morning_snack' | 'lunch' | 'afternoon_snack' | 'dinner'
export type PreferenceKind = 'like' | 'dislike' | 'allergy' | 'intolerance'
/** I 14 allergeni UE (backend `profiles/allergens.py`). */
export type Allergen =
  | 'gluten'
  | 'crustaceans'
  | 'eggs'
  | 'fish'
  | 'peanuts'
  | 'soy'
  | 'milk'
  | 'nuts'
  | 'celery'
  | 'mustard'
  | 'sesame'
  | 'sulphites'
  | 'lupin'
  | 'molluscs'

export interface FoodPreference {
  id: UUID
  kind: PreferenceKind
  label: string
  /** Vuoto se l'etichetta non corrisponde con sicurezza a un allergene. */
  allergen: Allergen | ''
}

export interface Profile {
  first_name: string
  last_name: string
  /** YYYY-MM-DD */
  birth_date: string | null
  age: number | null
  sex: Sex | ''
  height_cm: number | null
  /** Decimale serializzato ("61.5"). */
  weight_kg: string | null
  goals: Goal[]
  goals_note: string
  activity_level: ActivityLevel | ''
  sport_sessions_per_week: number | null
  conditions: string[]
  /** `null` finche' non ha risposto. */
  followed_by_nutritionist: boolean | null
  meal_slots: MealSlot[]
  household_size: number
  onboarding_completed: boolean
  preferences: FoodPreference[]
}

/** I campi che si salvano con PATCH /api/profile (le preferenze hanno la loro API). */
export type ProfileDraft = Omit<Profile, 'age' | 'onboarding_completed' | 'preferences'>
