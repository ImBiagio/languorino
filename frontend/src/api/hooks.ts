// Hook di TanStack Query per l'API. Una sezione per area dell'app, con le
// chiavi di cache tutte in `keys` cosi' le invalidazioni restano coerenti.

import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../lib/api'
import type {
  FoodPreference,
  Ingredient,
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
