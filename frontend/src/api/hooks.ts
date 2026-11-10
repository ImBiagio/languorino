// Hook di TanStack Query per l'API. Una sezione per area dell'app, con le
// chiavi di cache tutte in `keys` cosi' le invalidazioni restano coerenti.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../lib/api'
import type { FoodPreference, PreferenceKind, Profile, ProfileDraft, UUID } from '../lib/types'

export const keys = {
  profile: ['profile'] as const,
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
