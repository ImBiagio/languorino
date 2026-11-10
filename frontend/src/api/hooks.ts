// Hook di TanStack Query per l'API. Una sezione per area dell'app, con le
// chiavi di cache tutte in `keys` cosi' le invalidazioni restano coerenti.

import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../lib/api'
import type {
  FoodPreference,
  Ingredient,
  Job,
  JobStatus,
  Paginated,
  PreferenceKind,
  Profile,
  ProfileDraft,
  Recipe,
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

export function useRecipes(filters: RecipeFilters) {
  return useQuery({
    queryKey: keys.recipeList(filters),
    queryFn: () =>
      api.get<Paginated<RecipeSummary>>('/api/recipes', {
        q: filters.q || undefined,
        tag: filters.tag?.length ? filters.tag : undefined,
        max_minutes: filters.max_minutes,
        slot: filters.slot,
        page_size: 200,
      }),
    // Mentre si scrive nella ricerca resta il risultato di prima, senza lampi.
    placeholderData: keepPreviousData,
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
