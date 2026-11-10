import { getAccessToken } from '../lib/api'
import { getLanguage, getLanguages, setLanguage } from '../lib/i18n'
import { Segmented } from './ui'

/** Italiano / English: salva la scelta e ricarica la pagina tradotta. */
export function LanguageSwitcher({ className }: { className?: string }) {
  return (
    <Segmented
      value={getLanguage()}
      options={getLanguages().map((language) => ({ value: language.code, label: language.name }))}
      onChange={(code) => {
        if (code !== getLanguage()) void setLanguage(code, getAccessToken())
      }}
      className={className}
    />
  )
}
