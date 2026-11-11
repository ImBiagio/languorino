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
  /** `/media/...`: foto vera o disegnata dall'AI; vuota = disegno per categoria. */
  image: string | null
  image_source: '' | 'photo' | 'ai'
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
  /** Link di condivisione `/r/<token>`, se acceso (ADR 0012). */
  share_token: string | null
  copied_from: UUID | null
  created_at: string
}

/** La ricetta vista dal link pubblico. */
export interface SharedRecipe {
  id: UUID
  title: string
  image: string | null
  description: string
  servings: number
  prep_minutes: number
  cook_minutes: number
  total_minutes: number
  difficulty: Difficulty
  meal_slots: MealSlot[]
  keeps_days: number | null
  freezable: boolean
  steps: string[]
  tags: string[]
  allergens: Allergen[]
  main_category: Category
  ingredients: RecipeLine[]
  author: string
  is_mine: boolean
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
  kind:
    | 'import_recipes'
    | 'fridge_scan'
    | 'cook_ideas'
    | 'nutritionist_plan'
    | 'recipe_image'
    | 'interview'
  status: JobStatus
  result: {
    recipes?: ImportedRecipeDraft[]
    /** Perche' non c'e' nessuna ricetta (foto sfocata, non e' una ricetta). */
    problem?: string
    /** Dopo la conferma: le ricette create. */
    created?: UUID[]
    /** Foto del frigo: gli alimenti riconosciuti. */
    ingredients?: string[]
    /** Cosa cucino oggi: le ricette nuove scritte dall'LLM. */
    ideas?: RecipeSummary[]
    /** Piano del nutrizionista: la bozza creata dalla lettura. */
    nutritionist_plan?: UUID
    /** Intervista: la risposta, la trascrizione della voce e le proposte. */
    reply?: string
    heard?: string
    updates?: Partial<ProfileDraft>
    preferences?: { kind: PreferenceKind; label: string; allergen: string }[]
    done?: boolean
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
  /** Immagini delle ricette (ADR 0015): foto dal PDF, poi illustrazioni AI. */
  without_image: number
  images_status: '' | 'searching' | 'drawing' | 'done' | 'failed'
  images_pages_done: number
  images_found: number
  images_error: string
  created_at: string
  finished_at: string | null
}

/* ------------------------------------------------------- piano alimentare -- */

export type PrepMode = 'none' | 'evening_before' | 'every_2' | 'every_3' | 'weekend'
export type PlanStatus = 'generating' | 'draft' | 'active' | 'archived' | 'failed'

/** Le scelte della procedura "Nuovo piano" (backend `PlanSettingsSerializer`). */
export interface PlanPayload {
  start_date: string
  days: 7 | 14 | 21 | 28
  slots: MealSlot[]
  servings: number
  prep_mode: PrepMode
  minutes: number
  difficulty: Difficulty
  use_cookbook: boolean
  books: UUID[]
  include_tags: string[]
  exclude_tags: string[]
  goal_note: string
  nutritionist_plan: UUID | null
}

export interface PlannedMeal {
  id: number
  date: string
  slot: MealSlot
  recipe: RecipeSummary | null
  servings: number
  /** Il giorno in cui si cucina: prima di `date` se viene dal meal prep. */
  cooked_on: string
  /** Perche' il pasto e' vuoto o e' stato cambiato. */
  note: string
  eaten: boolean
}

export interface MealPlan {
  id: UUID
  start_date: string
  end_date: string
  days: number
  status: PlanStatus
  settings: {
    slots: MealSlot[]
    servings: number
    prep_mode: PrepMode
    minutes: number
    difficulty: Difficulty
    sources: { cookbook: boolean; books: UUID[] }
    include_tags: string[]
    exclude_tags: string[]
    goal_note: string
    nutritionist_plan?: UUID | null
  }
  /** Il piano del nutrizionista seguito, se c'e'. */
  nutritionist: { id: UUID; title: string } | null
  weeks_done: number
  weeks_total: number
  error: string
  created_at: string
  finished_at: string | null
}

export interface MealPlanDetail extends MealPlan {
  meals: PlannedMeal[]
}

/* ------------------------------------------------------------------ spesa -- */

export interface ShoppingItem {
  id: number
  label: string
  /** Decimale serializzato; `null` per "q.b." o voci a mano senza quantita'. */
  quantity: string | null
  unit: Unit | ''
  category: Category
  checked: boolean
  /** "Ce l'ho gia'": non va comprato. */
  in_pantry: boolean
  manual: boolean
  edited: boolean
  sources: { date: string; slot: MealSlot; recipe: string }[]
}

export interface ShoppingList {
  id: UUID
  title: string
  plan: UUID | null
  date_from: string | null
  date_to: string | null
  status: 'open' | 'done'
  /** Voci da comprare (senza quelle "ce l'ho gia'"). */
  item_count: number
  checked_count: number
  created_at: string
}

export interface ShoppingListDetail extends ShoppingList {
  items: ShoppingItem[]
}

/* -------------------------------------------------------- cosa cucino oggi -- */

export interface CookMatch {
  recipe: RecipeSummary
  /** Ingredienti principali che ci sono gia'. */
  have: string[]
  /** Ingredienti principali che mancano. */
  missing: string[]
}

export interface CookSuggestions {
  ingredients: string[]
  matches: CookMatch[]
  /** Il lavoro che scrive le idee nuove; `null` se non chieste o LLM spento. */
  job: Job | null
}

/* ---------------------------------------------- piano del nutrizionista -- */

export interface NutritionistRules {
  meals: { slot: MealSlot; options: string[] }[]
  weekly: { food: string; times: number }[]
  free_foods: string[]
  avoid_foods: string[]
  notes: string
}

export interface NutritionistPlan {
  id: UUID
  title: string
  status: 'draft' | 'confirmed'
  /** Alla lettera: solo le opzioni del nutrizionista. */
  strict: boolean
  valid_from: string | null
  valid_to: string | null
  rules: NutritionistRules
  files: { original_name: string; content_type: string }[]
  created_at: string
  updated_at: string
}
