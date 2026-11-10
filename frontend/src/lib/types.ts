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

/* ---------------------------------------------------------------- ricette -- */

export type Category =
  | 'produce'
  | 'meat'
  | 'fish'
  | 'dairy'
  | 'bakery'
  | 'pantry'
  | 'spices'
  | 'frozen'
  | 'drinks'
  | 'other'
export type Unit =
  | 'g'
  | 'kg'
  | 'ml'
  | 'l'
  | 'pz'
  | 'tbsp'
  | 'tsp'
  | 'cup'
  | 'pinch'
  | 'clove'
  | 'slice'
  | 'bunch'
  | 'can'
  | 'to_taste'
export type Difficulty = 'easy' | 'medium' | 'hard'

export interface Ingredient {
  id: UUID
  /** Nella lingua dell'interfaccia quando il catalogo ce l'ha. */
  name: string
  category: Category
  allergens: Allergen[]
  default_unit: Unit
  grams_per_piece: number | null
  staple: boolean
  /** Aggiunto dall'utente: reparto e allergeni non curati. */
  custom: boolean
}

export interface RecipeLine {
  id: number
  ingredient: Ingredient
  /** Decimale serializzato; `null` per "q.b." o quando non c'e'. */
  quantity: string | null
  unit: Unit
  note: string
  optional: boolean
}

/** Una preferenza del profilo che la ricetta tocca (allergia, intolleranza, antipatia). */
export interface RecipeWarning {
  id: UUID
  kind: PreferenceKind
  label: string
  allergen: Allergen | ''
}

export interface RecipeSummary {
  id: UUID
  title: string
  servings: number
  total_minutes: number
  difficulty: Difficulty
  meal_slots: MealSlot[]
  tags: string[]
  allergens: Allergen[]
  warnings: RecipeWarning[]
  /** Reparto dell'ingrediente principale: sceglie il disegno della card. */
  main_category: Category
  ingredient_count: number
  in_cookbook: boolean
  /** `draft`: letta da un ricettario PDF e non ancora rivista. */
  status: 'draft' | 'confirmed'
  /** Il ricettario PDF da cui viene, se viene da li'. */
  book: { id: UUID; title: string } | null
  updated_at: string
}

export interface Recipe extends RecipeSummary {
  description: string
  prep_minutes: number
  cook_minutes: number
  steps: string[]
  keeps_days: number | null
  freezable: boolean
  ingredients: RecipeLine[]
  source: string
  created_at: string
}

/** Una riga del form: dal catalogo (`ingredient_id`) o scritta a mano (`name`). */
export interface RecipeLinePayload {
  ingredient_id?: UUID | null
  name?: string
  quantity: string | null
  unit: Unit
  note: string
  optional: boolean
}

export type RecipePayload = Pick<
  Recipe,
  | 'title'
  | 'description'
  | 'servings'
  | 'prep_minutes'
  | 'cook_minutes'
  | 'difficulty'
  | 'meal_slots'
  | 'steps'
  | 'keeps_days'
  | 'freezable'
  | 'tags'
> & { ingredients: RecipeLinePayload[] }

export interface Tag {
  id: UUID
  name: string
  recipe_count: number
}

export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface RecipeFilters {
  /** Solo le ricette di un ricettario PDF (salvate o no). */
  book?: UUID
  q?: string
  tag?: string[]
  max_minutes?: number
  slot?: MealSlot
}

/* ------------------------------------------------------ lavori e import -- */

export type JobStatus = 'queued' | 'running' | 'ready' | 'confirmed' | 'failed'

/** Una ricetta letta da foto o PDF, prima della revisione (backend `recipes/importing.py`). */
export interface ImportedRecipeDraft {
  title: string
  description: string
  servings: number
  prep_minutes: number
  cook_minutes: number
  difficulty: Difficulty
  meal_slots: MealSlot[]
  keeps_days: number | null
  freezable: boolean
  steps: string[]
  tags: string[]
  ingredients: {
    ingredient_id: UUID | null
    name: string
    category: Category | null
    quantity: string | null
    unit: Unit
    note: string
    optional: boolean
  }[]
  /** I campi che l'LLM ha dedotto perche' il testo non li diceva. */
  inferred: string[]
}

export interface Job {
  id: UUID
  kind: 'import_recipes'
  status: JobStatus
  result: {
    recipes?: ImportedRecipeDraft[]
    /** Perche' non c'e' nessuna ricetta (foto sfocata, non e' una ricetta). */
    problem?: string
    /** Dopo la conferma: le ricette create. */
    created?: UUID[]
  }
  error: string
  files: { id: UUID; content_type: string; original_name: string; size: number }[]
  created_at: string
  started_at: string | null
  finished_at: string | null
}

/* ---------------------------------------------------------- ricettari -- */

export type BookStatus = 'queued' | 'reading' | 'ready' | 'failed'

/** Un ricettario PDF letto a pezzi (ADR 0006). */
export interface RecipeBook {
  id: UUID
  title: string
  original_name: string
  size: number
  page_count: number
  /** Fin dove e' arrivata la lettura. */
  pages_done: number
  status: BookStatus
  error: string
  recipe_count: number
  /** Quante delle sue ricette sono gia' nel ricettario dell'utente. */
  saved_count: number
  created_at: string
  finished_at: string | null
}
