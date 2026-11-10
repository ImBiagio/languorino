// Date del piano: sempre stringhe ISO "AAAA-MM-GG" (come le manda il backend),
// trasformate in Date locali solo per formattarle. Niente fusi orari di mezzo.

import { intlLocale } from '../../lib/i18n'

export function parseDay(iso: string): Date {
  const [year, month, day] = iso.split('-').map(Number)
  return new Date(year, month - 1, day)
}

export function isoDay(day: Date): string {
  const month = String(day.getMonth() + 1).padStart(2, '0')
  return `${day.getFullYear()}-${month}-${String(day.getDate()).padStart(2, '0')}`
}

export function addDays(iso: string, days: number): string {
  const day = parseDay(iso)
  day.setDate(day.getDate() + days)
  return isoDay(day)
}

export function todayIso(): string {
  return isoDay(new Date())
}

/** Il prossimo lunedi' (oggi stesso se e' lunedi'). */
export function nextMondayIso(): string {
  const day = new Date()
  const shift = (8 - day.getDay()) % 7
  day.setDate(day.getDate() + shift)
  return isoDay(day)
}

function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1)
}

/** "Lunedì 17 novembre". */
export function formatDayLong(iso: string): string {
  return capitalize(
    new Intl.DateTimeFormat(intlLocale(), {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
    }).format(parseDay(iso)),
  )
}

/** "lun 17". */
export function formatDayShort(iso: string): string {
  return new Intl.DateTimeFormat(intlLocale(), { weekday: 'short', day: 'numeric' }).format(
    parseDay(iso),
  )
}

/** "lunedì" (per "cucinato lunedì"). */
export function formatWeekday(iso: string): string {
  return new Intl.DateTimeFormat(intlLocale(), { weekday: 'long' }).format(parseDay(iso))
}

/** "17 – 23 novembre" o "28 novembre – 4 dicembre". */
export function formatRange(start: string, end: string): string {
  const format = new Intl.DateTimeFormat(intlLocale(), { day: 'numeric', month: 'long' })
  return format.formatRange
    ? format.formatRange(parseDay(start), parseDay(end))
    : `${start} – ${end}`
}
