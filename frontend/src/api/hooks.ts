// Hook di TanStack Query per l'API. Una sezione per area dell'app, con le
// chiavi di cache tutte in `keys` cosi' le invalidazioni restano coerenti.

import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../lib/api'
import type {
  CookSuggestions,
  FoodPreference,
  Ingredient,
  Job,
  JobStatus,
  MealPlan,
  MealPlanDetail,
  NutritionistPlan,
  Paginated,
  PlanPayload,
  PlannedMeal,
  PreferenceKind,
  Profile,
  ProfileDraft,
  Recipe,
  RecipeBook,
  RecipeFilters,
  RecipePayload,
  RecipeSummary,
  SharedRecipe,
  ShoppingItem,
  ShoppingList,
  ShoppingListDetail,
  Tag,
  UUID,
} from '../lib/types'

export const keys = {
  profile: ['profile'] as const,
  recipes: ['recipes'] as const,
  recipeList: (filters: RecipeFilters) => ['recipes', 'list', filters] as const,
  recipe: (id: UUID) => ['recipes', 'detail', id] as const,
  tags: ['tags'] as const,
  ingredients: (query: string) => ['ingredients', query] as const,
  jobs: ['jobs'] as const,
  jobList: (statuses: JobStatus[], kind?: Job['kind']) => ['jobs', 'list', statuses, kind] as const,
  job: (id: UUID) => ['jobs', 'detail', id] as const,
  books: ['books'] as const,
  book: (id: UUID) => ['books', id] as const,
  plans: ['plans'] as const,
  plan: (id: UUID) => ['plans', 'detail', id] as const,
  currentPlan: ['plans', 'current'] as const,
  shoppingLists: ['shopping'] as const,
  shoppingList: (id: UUID) => ['shopping', 'detail', id] as const,
  nutritionistPlans: ['nutritionist-plans'] as const,
  nutritionistPlan: (id: UUID) => ['nutritionist-plans', 'detail', id] as const,
}

/* ------------------------------------------------------ profilo alimentare -- */

export function useProfile() {
  return useQuery({ queryKey: keys.profile, queryFn: () => api.get<Profile>('/api/profile') })
}

export function useUpdateProfile() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (changes: Partial<ProfileDraft>) => api.patch<Profile>('/api/profile', changes),
    onSuccess: (profile) => client.setQueryData(keys.profile, profile),
  })
}

/** Fine del wizard: da qui l'app apre la home. */
export function useCompleteOnboarding() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => api.post<Profile>('/api/profile/complete'),
    onSuccess: (profile) => client.setQueryData(keys.profile, profile),
  })
}

/**
 * Le preferenze si salvano subito, una per tocco: il profilo in cache si
 * aggiorna a mano, senza ricaricarlo tutto (e senza perdere un form a meta').
 */
export function useAddPreference() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: { kind: PreferenceKind; label: string; allergen?: string }) =>
      api.post<FoodPreference>('/api/profile/preferences', body),
    onSuccess: (preference) =>
      client.setQueryData<Profile>(keys.profile, (profile) =>
        profile && !profile.preferences.some((item) => item.id === preference.id)
          ? { ...profile, preferences: [...profile.preferences, preference] }
          : profile,
      ),
  })
}

export function useRemovePreference() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: UUID) => api.delete<void>(`/api/profile/preferences/${id}`),
    onSuccess: (_data, id) =>
      client.setQueryData<Profile>(keys.profile, (profile) =>
        profile
          ? { ...profile, preferences: profile.preferences.filter((item) => item.id !== id) }
          : profile,
      ),
  })
}

/* ---------------------------------------------------------------- ricette -- */

export function useRecipes(filters: RecipeFilters, options: { poll?: boolean } = {}) {
  return useQuery({
    queryKey: keys.recipeList(filters),
    queryFn: () =>
      api.get<Paginated<RecipeSummary>>('/api/recipes', {
        book: filters.book,
        q: filters.q || undefined,
        tag: filters.tag?.length ? filters.tag : undefined,
        max_minutes: filters.max_minutes,
        slot: filters.slot,
        page_size: 200,
      }),
    // Mentre si scrive nella ricerca resta il risultato di prima, senza lampi.
    placeholderData: keepPreviousData,
    // Un ricettario in lettura: le ricette arrivano man mano.
    refetchInterval: options.poll ? 4000 : false,
  })
}

/** Una ricetta di un ricettario PDF entra nel ricettario dell'utente. */
export function useSaveToCookbook() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: UUID) => api.post<Recipe>(`/api/recipes/${id}/save`),
    onSuccess: (recipe) => {
      client.setQueryData(keys.recipe(recipe.id), recipe)
      void client.invalidateQueries({ queryKey: [...keys.recipes, 'list'] })
      void client.invalidateQueries({ queryKey: keys.books })
      void client.invalidateQueries({ queryKey: keys.tags })
    },
  })
}

export function useRecipe(id: UUID | undefined) {
  return useQuery({
    queryKey: keys.recipe(id!),
    queryFn: () => api.get<Recipe>(`/api/recipes/${id}`),
    enabled: Boolean(id),
  })
}

export function useSaveRecipe() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...body }: RecipePayload & { id?: UUID }) =>
      id ? api.patch<Recipe>(`/api/recipes/${id}`, body) : api.post<Recipe>('/api/recipes', body),
    onSuccess: (recipe) => {
      client.setQueryData(keys.recipe(recipe.id), recipe)
      // Elenchi e tag cambiano con la ricetta (titolo, ingredienti, conteggi).
      void client.invalidateQueries({ queryKey: [...keys.recipes, 'list'] })
      void client.invalidateQueries({ queryKey: keys.tags })
    },
  })
}

export function useDeleteRecipe() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: UUID) => api.delete<void>(`/api/recipes/${id}`),
    onSuccess: (_data, id) => {
      client.removeQueries({ queryKey: keys.recipe(id) })
      void client.invalidateQueries({ queryKey: [...keys.recipes, 'list'] })
      void client.invalidateQueries({ queryKey: keys.tags })
    },
  })
}

export function useTags() {
  return useQuery({ queryKey: keys.tags, queryFn: () => api.get<Tag[]>('/api/tags') })
}

/** Suggerimenti del catalogo mentre si scrive un ingrediente (da 2 lettere). */
export function useIngredientSearch(query: string) {
  const trimmed = query.trim()
  return useQuery({
    queryKey: keys.ingredients(trimmed.toLowerCase()),
    queryFn: () => api.get<Ingredient[]>('/api/ingredients', { q: trimmed }),
    enabled: trimmed.length >= 2,
    staleTime: 5 * 60_000,
  })
}

/* ------------------------------------------------------ lavori e import -- */

const WORKING: JobStatus[] = ['queued', 'running']

/** I lavori in corso o da rivedere: il banner sopra il ricettario. */
/**
 * I lavori dell'utente per stato e, quasi sempre, per tipo: un turno
 * dell'intervista o un'idea del frigo restano "ready" e non sono import da
 * rivedere (mostravano "Lettura finita" sopra il ricettario).
 */
export function useJobs(statuses: JobStatus[], kind?: Job['kind']) {
  return useQuery({
    queryKey: keys.jobList(statuses, kind),
    queryFn: () => api.get<Job[]>('/api/jobs', { status: statuses, kind }),
    // Finche' qualcosa e' in lavorazione si ricontrolla da soli.
    refetchInterval: (query) =>
      query.state.data?.some((job) => WORKING.includes(job.status)) ? 3000 : false,
  })
}

export function useJob(id: UUID | undefined) {
  return useQuery({
    queryKey: keys.job(id!),
    queryFn: () => api.get<Job>(`/api/jobs/${id}`),
    enabled: Boolean(id),
    // L'intervista e' una chiacchierata: si controlla piu' spesso.
    refetchInterval: (query) =>
      query.state.data && WORKING.includes(query.state.data.status)
        ? query.state.data.kind === 'interview'
          ? 800
          : 2000
        : false,
  })
}

export function useStartImport() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (files: File[]) => {
      const form = new FormData()
      form.append('kind', 'import_recipes')
      for (const file of files) form.append('files', file)
      return api.post<Job>('/api/jobs', form)
    },
    onSuccess: (job) => {
      client.setQueryData(keys.job(job.id), job)
      void client.invalidateQueries({ queryKey: keys.jobs })
    },
  })
}

export function useRetryJob() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: UUID) => api.post<Job>(`/api/jobs/${id}/retry`),
    onSuccess: (job) => {
      client.setQueryData(keys.job(job.id), job)
      void client.invalidateQueries({ queryKey: keys.jobs })
    },
  })
}

export function useDiscardJob() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: UUID) => api.delete<void>(`/api/jobs/${id}`),
    onSuccess: (_data, id) => {
      client.removeQueries({ queryKey: keys.job(id) })
      void client.invalidateQueries({ queryKey: keys.jobs })
    },
  })
}

export function useConfirmImport() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, recipes }: { id: UUID; recipes: RecipePayload[] }) =>
      api.post<Job>(`/api/jobs/${id}/confirm`, { recipes }),
    onSuccess: (job) => {
      client.setQueryData(keys.job(job.id), job)
      void client.invalidateQueries({ queryKey: keys.jobs })
      void client.invalidateQueries({ queryKey: [...keys.recipes, 'list'] })
      void client.invalidateQueries({ queryKey: keys.tags })
    },
  })
}

/* ---------------------------------------------------------- ricettari -- */

const READING = ['queued', 'reading']

export function useBooks() {
  return useQuery({
    queryKey: keys.books,
    queryFn: () => api.get<RecipeBook[]>('/api/recipe-books'),
    refetchInterval: (query) =>
      query.state.data?.some((book) => READING.includes(book.status)) ? 4000 : false,
  })
}

export function useBook(id: UUID | undefined) {
  return useQuery({
    queryKey: keys.book(id!),
    queryFn: () => api.get<RecipeBook>(`/api/recipe-books/${id}`),
    enabled: Boolean(id),
    refetchInterval: (query) =>
      query.state.data && READING.includes(query.state.data.status) ? 3000 : false,
  })
}

export function useUploadBook() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return api.post<RecipeBook>('/api/recipe-books', form)
    },
    onSuccess: (book) => {
      client.setQueryData(keys.book(book.id), book)
      void client.invalidateQueries({ queryKey: keys.books })
    },
  })
}

export function useRetryBook() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: UUID) => api.post<RecipeBook>(`/api/recipe-books/${id}/retry`),
    onSuccess: (book) => {
      client.setQueryData(keys.book(book.id), book)
      void client.invalidateQueries({ queryKey: keys.books })
    },
  })
}

export function useRenameBook() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, title }: { id: UUID; title: string }) =>
      api.patch<RecipeBook>(`/api/recipe-books/${id}`, { title }),
    onSuccess: (book) => {
      client.setQueryData(keys.book(book.id), book)
      void client.invalidateQueries({ queryKey: keys.books })
      void client.invalidateQueries({ queryKey: [...keys.recipes, 'list'] })
    },
  })
}

export function useDeleteBook() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: UUID) => api.delete<void>(`/api/recipe-books/${id}`),
    onSuccess: (_data, id) => {
      client.removeQueries({ queryKey: keys.book(id) })
      void client.invalidateQueries({ queryKey: keys.books })
      void client.invalidateQueries({ queryKey: [...keys.recipes, 'list'] })
    },
  })
}

/* ------------------------------------------------------- piano alimentare -- */

export function usePlans() {
  return useQuery({
    queryKey: keys.plans,
    queryFn: () => api.get<MealPlan[]>('/api/plans'),
    refetchInterval: (query) =>
      query.state.data?.some((plan) => plan.status === 'generating') ? 4000 : false,
  })
}

export function usePlan(id: UUID | undefined) {
  return useQuery({
    queryKey: keys.plan(id!),
    queryFn: () => api.get<MealPlanDetail>(`/api/plans/${id}`),
    enabled: Boolean(id),
    refetchInterval: (query) => (query.state.data?.status === 'generating' ? 3000 : false),
  })
}

/** Il piano attivo per oggi (o il prossimo); `undefined` se non ce n'e' (204). */
export function useCurrentPlan() {
  return useQuery({
    queryKey: keys.currentPlan,
    queryFn: () =>
      api.get<MealPlanDetail | undefined>('/api/plans/current').then((plan) => plan ?? null),
  })
}

function usePlanMutation<T>(fn: (arg: T) => Promise<MealPlanDetail>) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: (plan) => {
      client.setQueryData(keys.plan(plan.id), plan)
      void client.invalidateQueries({ queryKey: keys.plans })
    },
  })
}

export function useCreatePlan() {
  return usePlanMutation((body: PlanPayload) => api.post<MealPlanDetail>('/api/plans', body))
}

export function useActivatePlan() {
  return usePlanMutation((id: UUID) => api.post<MealPlanDetail>(`/api/plans/${id}/activate`))
}

export function useRegeneratePlan() {
  return usePlanMutation((id: UUID) => api.post<MealPlanDetail>(`/api/plans/${id}/regenerate`))
}

export function useRetryPlan() {
  return usePlanMutation((id: UUID) => api.post<MealPlanDetail>(`/api/plans/${id}/retry`))
}

export function useDeletePlan() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: UUID) => api.delete<void>(`/api/plans/${id}`),
    onSuccess: (_data, id) => {
      client.removeQueries({ queryKey: keys.plan(id) })
      void client.invalidateQueries({ queryKey: keys.plans })
    },
  })
}

export function useUpdateMeal(planId: UUID) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({
      id,
      ...body
    }: {
      id: number
      recipe_id?: UUID | null
      servings?: number
      cooked_on?: string
      eaten?: boolean
    }) => api.patch<PlannedMeal>(`/api/plans/${planId}/meals/${id}`, body),
    onSuccess: (meal) => {
      client.setQueryData<MealPlanDetail>(keys.plan(planId), (plan) =>
        plan ? { ...plan, meals: plan.meals.map((m) => (m.id === meal.id ? meal : m)) } : plan,
      )
      void client.invalidateQueries({ queryKey: keys.currentPlan })
    },
  })
}

/* ------------------------------------------------------------------ spesa -- */

export function useShoppingLists() {
  return useQuery({
    queryKey: keys.shoppingLists,
    queryFn: () => api.get<ShoppingList[]>('/api/shopping'),
  })
}

export function useShoppingList(id: UUID | undefined) {
  return useQuery({
    queryKey: keys.shoppingList(id!),
    queryFn: () => api.get<ShoppingListDetail>(`/api/shopping/${id}`),
    enabled: Boolean(id),
  })
}

function useListMutation<T>(fn: (arg: T) => Promise<ShoppingListDetail>) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: (list) => {
      client.setQueryData(keys.shoppingList(list.id), list)
      void client.invalidateQueries({ queryKey: keys.shoppingLists, exact: true })
    },
  })
}

export function useCreateShoppingList() {
  return useListMutation(
    (body: { plan?: UUID; date_from?: string; date_to?: string; title?: string }) =>
      api.post<ShoppingListDetail>('/api/shopping', body),
  )
}

export function useRegenerateShoppingList() {
  return useListMutation((id: UUID) =>
    api.post<ShoppingListDetail>(`/api/shopping/${id}/regenerate`),
  )
}

export function useUpdateShoppingList() {
  return useListMutation(
    ({ id, ...body }: { id: UUID; title?: string; status?: 'open' | 'done' }) =>
      api.patch<ShoppingListDetail>(`/api/shopping/${id}`, body),
  )
}

export function useDeleteShoppingList() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: UUID) => api.delete<void>(`/api/shopping/${id}`),
    onSuccess: (_data, id) => {
      client.removeQueries({ queryKey: keys.shoppingList(id) })
      void client.invalidateQueries({ queryKey: keys.shoppingLists, exact: true })
    },
  })
}

/** Aggiorna una voce nella cache della lista (e i contatori). */
function patchItem(
  list: ShoppingListDetail | undefined,
  id: number,
  change: (item: ShoppingItem) => ShoppingItem | null,
): ShoppingListDetail | undefined {
  if (!list) return list
  const items = list.items.flatMap((item) => {
    if (item.id !== id) return [item]
    const next = change(item)
    return next ? [next] : []
  })
  const toBuy = items.filter((item) => !item.in_pantry)
  return {
    ...list,
    items,
    item_count: toBuy.length,
    checked_count: toBuy.filter((item) => item.checked).length,
  }
}

export function useAddShoppingItem(listId: UUID) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: { label: string; quantity?: string | null; unit?: string }) =>
      api.post<ShoppingItem>(`/api/shopping/${listId}/items`, body),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.shoppingList(listId) }),
  })
}

/**
 * Spuntare deve essere istantaneo anche con il telefono in un angolo del
 * supermercato: la cache cambia subito e torna indietro se la richiesta fallisce.
 */
export function useUpdateShoppingItem(listId: UUID) {
  const client = useQueryClient()
  const key = keys.shoppingList(listId)
  return useMutation({
    mutationFn: ({ id, ...body }: { id: number } & Partial<ShoppingItem>) =>
      api.patch<ShoppingItem>(`/api/shopping/${listId}/items/${id}`, body),
    onMutate: async ({ id, ...body }) => {
      await client.cancelQueries({ queryKey: key })
      const before = client.getQueryData<ShoppingListDetail>(key)
      client.setQueryData<ShoppingListDetail>(key, (list) =>
        patchItem(list, id, (item) => ({ ...item, ...body })),
      )
      return { before }
    },
    onError: (_error, _vars, context) => {
      if (context?.before) client.setQueryData(key, context.before)
    },
    onSuccess: (item) => {
      client.setQueryData<ShoppingListDetail>(key, (list) => patchItem(list, item.id, () => item))
    },
  })
}

export function useDeleteShoppingItem(listId: UUID) {
  const client = useQueryClient()
  const key = keys.shoppingList(listId)
  return useMutation({
    mutationFn: (id: number) => api.delete<void>(`/api/shopping/${listId}/items/${id}`),
    onSuccess: (_data, id) =>
      client.setQueryData<ShoppingListDetail>(key, (list) => patchItem(list, id, () => null)),
  })
}

/* -------------------------------------------------------- cosa cucino oggi -- */

export function useScanFridge() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (files: File[]) => {
      const form = new FormData()
      for (const file of files) form.append('files', file)
      return api.post<Job>('/api/cook-today/scan', form)
    },
    onSuccess: (job) => client.setQueryData(keys.job(job.id), job),
  })
}

export function useCookSuggestions() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      ingredients: string[]
      slot?: string | null
      minutes?: number | null
      servings: number
      include_books: boolean
    }) => api.post<CookSuggestions>('/api/cook-today/suggest', body),
    onSuccess: (result) => {
      if (result.job) client.setQueryData(keys.job(result.job.id), result.job)
    },
  })
}

/* ------------------------------------------- piano del nutrizionista -- */

export function useNutritionistPlans() {
  return useQuery({
    queryKey: keys.nutritionistPlans,
    queryFn: () => api.get<NutritionistPlan[]>('/api/nutritionist-plans'),
  })
}

export function useNutritionistPlan(id: UUID | undefined) {
  return useQuery({
    queryKey: keys.nutritionistPlan(id!),
    queryFn: () => api.get<NutritionistPlan>(`/api/nutritionist-plans/${id}`),
    enabled: Boolean(id),
  })
}

/** PDF o foto del piano: parte la lettura, la bozza arriva col job. */
export function useReadNutritionistPlan() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (files: File[]) => {
      const form = new FormData()
      for (const file of files) form.append('files', file)
      return api.post<Job>('/api/nutritionist-plans', form)
    },
    onSuccess: (job) => client.setQueryData(keys.job(job.id), job),
  })
}

function useNutritionistMutation<T>(fn: (input: T) => Promise<NutritionistPlan>) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: (plan) => {
      client.setQueryData(keys.nutritionistPlan(plan.id), plan)
      void client.invalidateQueries({ queryKey: keys.nutritionistPlans, exact: true })
    },
  })
}

export function useUpdateNutritionistPlan() {
  return useNutritionistMutation(({ id, ...changes }: Partial<NutritionistPlan> & { id: UUID }) =>
    api.patch<NutritionistPlan>(`/api/nutritionist-plans/${id}`, changes),
  )
}

export function useConfirmNutritionistPlan() {
  return useNutritionistMutation((id: UUID) =>
    api.post<NutritionistPlan>(`/api/nutritionist-plans/${id}/confirm`),
  )
}

export function useDeleteNutritionistPlan() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: UUID) => api.delete<void>(`/api/nutritionist-plans/${id}`),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.nutritionistPlans }),
  })
}

/* ------------------------------------------------ immagini delle ricette -- */

function useRecipeImageMutation<T>(fn: (input: T) => Promise<Recipe>) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: (recipe) => {
      client.setQueryData(keys.recipe(recipe.id), recipe)
      void client.invalidateQueries({ queryKey: [...keys.recipes, 'list'] })
    },
  })
}

export function useUploadRecipeImage() {
  return useRecipeImageMutation(({ id, file }: { id: UUID; file: File }) => {
    const form = new FormData()
    form.append('file', file)
    return api.post<Recipe>(`/api/recipes/${id}/image`, form)
  })
}

export function useRemoveRecipeImage() {
  return useRecipeImageMutation((id: UUID) => api.delete<Recipe>(`/api/recipes/${id}/image`))
}

/** Gemini disegna l'immagine: torna il job da seguire. */
export function useDrawRecipeImage() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: UUID) => api.post<Job>(`/api/recipes/${id}/image/draw`),
    onSuccess: (job) => client.setQueryData(keys.job(job.id), job),
  })
}

/* --------------------------------------------- condivisione delle ricette -- */

export function useShareRecipe() {
  return useRecipeImageMutation(({ id, renew }: { id: UUID; renew?: boolean }) =>
    api.post<Recipe>(`/api/recipes/${id}/share`, { renew: Boolean(renew) }),
  )
}

export function useUnshareRecipe() {
  return useRecipeImageMutation((id: UUID) => api.delete<Recipe>(`/api/recipes/${id}/share`))
}

/**
 * ``viewer``: chi guarda (id o "anon"), noto solo a sessione caricata. Prima
 * la richiesta partirebbe senza token e il proprietario risulterebbe ospite.
 */
export function useSharedRecipe(token: string | undefined, viewer: string | undefined) {
  return useQuery({
    queryKey: ['shared-recipe', token, viewer],
    queryFn: () => api.get<SharedRecipe>(`/api/shared/recipes/${token}`),
    enabled: Boolean(token && viewer),
    retry: false,
  })
}

export function useCopySharedRecipe() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (token: string) => api.post<Recipe>(`/api/shared/recipes/${token}/copy`),
    onSuccess: (recipe) => {
      client.setQueryData(keys.recipe(recipe.id), recipe)
      void client.invalidateQueries({ queryKey: [...keys.recipes, 'list'] })
      void client.invalidateQueries({ queryKey: keys.tags })
    },
  })
}

/* --------------------------------------------------------- intervista -- */

export type InterviewMessage = { role: 'assistant' | 'user'; text: string }

/** Un turno dell'intervista: la conversazione e, se si parla, la registrazione. */
export function useInterviewTurn() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ messages, audio }: { messages: InterviewMessage[]; audio?: File }) => {
      if (!audio) return api.post<Job>('/api/profile/interview', { messages })
      const form = new FormData()
      form.append('messages', JSON.stringify(messages))
      form.append('audio', audio)
      return api.post<Job>('/api/profile/interview', form)
    },
    onSuccess: (job) => client.setQueryData(keys.job(job.id), job),
  })
}

/** Apre una conversazione a voce in tempo reale: token monouso e modello. */
export function useStartLiveInterview() {
  return useMutation({
    mutationFn: () => api.post<{ token: string; model: string }>('/api/profile/interview/live'),
  })
}

/** Una chiamata agli strumenti della voce, ripulita dal backend. */
export function cleanLiveCall(name: string, args: Record<string, unknown>) {
  return api.post<{
    updates: Partial<ProfileDraft>
    preferences: { kind: PreferenceKind; label: string; allergen: string }[]
  }>('/api/profile/interview/proposal', { name, args })
}

/** Idee nuove per un pasto del piano (job): si sceglie poi con useUpdateMeal. */
export function useMealIdeas(planId: UUID) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ mealId, hint }: { mealId: number; hint: string }) =>
      api.post<Job>(`/api/plans/${planId}/meals/${mealId}/ideas`, { hint }),
    onSuccess: (job) => client.setQueryData(keys.job(job.id), job),
  })
}
