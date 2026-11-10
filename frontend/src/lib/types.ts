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
