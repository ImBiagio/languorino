import { gettext, intlLocale } from './i18n'
import type { Money } from './types'

export function formatDate(isoDate: string): string {
  const [year, month, day] = isoDate.split('-').map(Number)
  return new Intl.DateTimeFormat(intlLocale(), {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(new Date(year, month - 1, day))
}

/** Data e ora di un istante ISO, per gli avvisi. */
export function formatDateTime(iso: string): string {
  return new Intl.DateTimeFormat(intlLocale(), {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(iso))
}

/** Giorni da oggi a una data YYYY-MM-DD (negativi se passata). */
export function daysUntil(isoDate: string): number {
  const [year, month, day] = isoDate.split('-').map(Number)
  const today = new Date()
  const start = new Date(today.getFullYear(), today.getMonth(), today.getDate())
  return Math.round((new Date(year, month - 1, day).getTime() - start.getTime()) / 86_400_000)
}

/** Prezzo in euro; il Decimal arriva come stringa e resta stringa fino a qui. */
export function formatPrice(value: Money | null | undefined): string {
  if (value === null || value === undefined || value === '') return ''
  return new Intl.NumberFormat(intlLocale(), { style: 'currency', currency: 'EUR' }).format(
    Number(value),
  )
}

/**
 * Da quello che si scrive nel campo ("19,90", "1.299,00", "20") al Decimal
 * dell'API ("19.90"). Vuoto o illeggibile diventa `null`.
 */
export function parsePrice(raw: string): Money | null {
  const text = raw.trim().replace(/\s|€/g, '')
  if (!text) return null
  const lastComma = text.lastIndexOf(',')
  const lastDot = text.lastIndexOf('.')
  const decimalSep = lastComma > lastDot ? ',' : '.'
  const thousandSep = decimalSep === ',' ? '.' : ','
  const normalized = text.split(thousandSep).join('').replace(decimalSep, '.')
  const value = Number(normalized)
  if (!Number.isFinite(value) || value < 0) return null
  return value.toFixed(2)
}

/** Il Decimal dell'API come lo si riscrive nel campo: "19.90" → "19,90" in italiano. */
export function priceInput(value: Money | null): string {
  if (!value) return ''
  return intlLocale().startsWith('it') ? value.replace('.', ',') : value
}

/** "Anna", "Anna e Luca", "Anna, Luca e Marco". */
export function joinNames(names: string[]): string {
  if (names.length <= 1) return names[0] ?? ''
  return `${names.slice(0, -1).join(', ')} ${gettext('e')} ${names[names.length - 1]}`
}

/** Il dominio di un link, per mostrarlo al posto dell'URL intero. */
export function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

export function initials(name: string): string {
  return name
    .split(/[\s@.]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
}
