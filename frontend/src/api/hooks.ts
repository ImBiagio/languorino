// Hook di TanStack Query per l'API. Una sezione per area dell'app, con le
// chiavi di cache tutte in `keys` cosi' le invalidazioni restano coerenti.

import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../lib/api'
import type {
  FoodPreference,
  Ingredient,
  Job,
  JobStatus,
  MealPlan,
  MealPlanDetail,
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
  jobList: (statuses: JobStatus[]) => ['jobs', 'list', statuses] as const,
  job: (id: UUID) => ['jobs', 'detail', id] as const,
  books: ['books'] as const,
  book: (id: UUID) => ['books', id] as const,
  plans: ['plans'] as const,
  plan: (id: UUID) => ['plans', 'detail', id] as const,
  currentPlan: ['plans', 'current'] as const,
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
export function useJobs(statuses: JobStatus[]) {
  return useQuery({
    queryKey: keys.jobList(statuses),
    queryFn: () => api.get<Job[]>('/api/jobs', { status: statuses }),
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
    refetchInterval: (query) =>
      query.state.data && WORKING.includes(query.state.data.status) ? 2000 : false,
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
