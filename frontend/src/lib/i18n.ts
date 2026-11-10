// Traduzioni con lo standard di Django (ADR 0001). Le stringhe del frontend sono
// msgid italiani nel dominio `djangojs` di backend/locale; `makemessages` le
// estrae da questi sorgenti e `/api/i18n/catalog` (JSONCatalog) le restituisce
// nella lingua attiva. Le funzioni hanno nome e firma di quelle del catalogo
// JavaScript di Django, cosi' xgettext le riconosce senza configurazione.
//
// Regole per chi scrive codice: a gettext() & co. si passano solo stringhe
// letterali (niente variabili, niente template literal); i valori entrano con
// interpolate(). Mai una chiamata dentro `${...}` di un template literal.

type CatalogEntry = string | string[]

interface CatalogResponse {
  catalog: Record<string, CatalogEntry>
  language: string
  explicit: boolean
  languages: { code: string; name: string }[]
}

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string) || window.location.origin
const CONTEXT_SEPARATOR = '\x04'

let catalog: Record<string, CatalogEntry> = {}
let language = 'it'
let explicit = false
let languages: { code: string; name: string }[] = [
  { code: 'it', name: 'Italiano' },
  { code: 'en', name: 'English' },
]

/**
 * Da chiamare prima di montare l'app: le costanti di modulo che usano
 * gettext() si valutano all'import, quindi l'app va importata dopo.
 * Se il catalogo non arriva si resta sui msgid, cioe' in italiano.
 */
export async function loadCatalog(): Promise<void> {
  try {
    const response = await fetch(`${BASE_URL}/api/i18n/catalog`, { credentials: 'include' })
    if (!response.ok) return
    const data = (await response.json()) as CatalogResponse
    catalog = data.catalog ?? {}
    language = data.language || 'it'
    explicit = Boolean(data.explicit)
    if (data.languages?.length) languages = data.languages
  } catch {
    // Rete giu' o backend spento: interfaccia in italiano.
  } finally {
    document.documentElement.lang = language
  }
}

export function getLanguage(): string {
  return language
}

/** true se la lingua e' stata scelta (cookie), false se dedotta dal browser. */
export function isExplicitLanguage(): boolean {
  return explicit
}

export function getLanguages() {
  return languages
}

/** Locale per Intl (date, importi): inglese britannico per avere giorno/mese. */
export function intlLocale(): string {
  return language === 'en' ? 'en-GB' : 'it-IT'
}

/**
 * Cambia lingua: il backend scrive il cookie (e `User.language` se c'e' il
 * login), poi si ricarica la pagina cosi' anche le costanti si ritraducono.
 */
export async function setLanguage(code: string, accessToken?: string | null): Promise<void> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`
  await fetch(`${BASE_URL}/api/i18n/language`, {
    method: 'POST',
    credentials: 'include',
    headers,
    body: JSON.stringify({ language: code }),
  })
  window.location.reload()
}

// In italiano e in inglese il plurale e' lo stesso: una forma per 1, l'altra
// per tutto il resto. Il catalogo porta anche la formula, ma valutarla
// richiederebbe eval: con due lingue basta questa.
const pluralIndex = (count: number) => (count === 1 ? 0 : 1)

export function gettext(msgid: string): string {
  const value = catalog[msgid]
  if (value === undefined) return msgid
  return typeof value === 'string' ? value : value[0]
}

export function ngettext(singular: string, plural: string, count: number): string {
  const value = catalog[singular]
  if (value === undefined || typeof value === 'string') {
    return count === 1 ? singular : plural
  }
  return value[pluralIndex(count)] ?? (count === 1 ? singular : plural)
}

export function pgettext(context: string, msgid: string): string {
  const translated = gettext(context + CONTEXT_SEPARATOR + msgid)
  return translated.includes(CONTEXT_SEPARATOR) ? msgid : translated
}

export function npgettext(
  context: string,
  singular: string,
  plural: string,
  count: number,
): string {
  const translated = ngettext(
    context + CONTEXT_SEPARATOR + singular,
    context + CONTEXT_SEPARATOR + plural,
    count,
  )
  return translated.includes(CONTEXT_SEPARATOR) ? ngettext(singular, plural, count) : translated
}

/**
 * Come `interpolate` di Django: `%s` posizionali con un array, oppure
 * `%(nome)s` con un oggetto e `named = true`.
 */
export function interpolate(
  format: string,
  values: readonly unknown[] | Record<string, unknown>,
  named = false,
): string {
  if (named) {
    const map = values as Record<string, unknown>
    return format.replace(/%\(\w+\)s/g, (match) => String(map[match.slice(2, -2)]))
  }
  const list = [...(values as readonly unknown[])]
  return format.replace(/%s/g, () => String(list.shift()))
}
