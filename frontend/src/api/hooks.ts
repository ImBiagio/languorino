// Hook di TanStack Query per l'API. Una sezione per area dell'app, con le
// chiavi di cache tutte in `keys` cosi' le invalidazioni restano coerenti.
//
// Esempio di sezione:
//
//   export function useThings() {
//     return useQuery({ queryKey: keys.things, queryFn: () => api.get<Thing[]>('/api/things') })
//   }
//
//   export function useSaveThing() {
//     const client = useQueryClient()
//     return useMutation({
//       mutationFn: ({ id, ...body }: ThingPayload & { id?: UUID }) =>
//         id ? api.patch<Thing>(`/api/things/${id}`, body) : api.post<Thing>('/api/things', body),
//       onSuccess: () => client.invalidateQueries({ queryKey: keys.things }),
//     })
//   }

export const keys = {} as const
