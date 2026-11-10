import clsx from 'clsx'
import type { CSSProperties, ReactNode } from 'react'
import { useEffect, useState } from 'react'

import { initials } from '../lib/format'
import { useCloseOnEscape } from '../lib/hooks'
import { gettext } from '../lib/i18n'

/* ---------------------------------------------------------------- icone -- */

export function Icon({
  name,
  size = 24,
  filled,
  className,
  style,
}: {
  name: string
  size?: number
  filled?: boolean
  className?: string
  style?: CSSProperties
}) {
  return (
    <span
      aria-hidden
      className={clsx('icon', filled && 'icon-filled', className)}
      style={{ fontSize: size, width: size, height: size, ...style }}
    >
      {name}
    </span>
  )
}

/** Pastiglia rotonda piena del colore della categoria, glifo bianco. */
export function IconCircle({
  name,
  color,
  size = 44,
  className,
}: {
  name: string
  color: string
  size?: number
  className?: string
}) {
  return (
    <span
      className={clsx('inline-flex shrink-0 items-center justify-center rounded-pill', className)}
      style={{ width: size, height: size, background: color }}
    >
      <Icon name={name} size={Math.round(size * 0.52)} className="text-white" />
    </span>
  )
}

/** Pulsante rotondo con solo l'icona: chiudi, elimina, menu. */
export function IconButton({
  icon,
  label,
  onClick,
  size = 'sm',
  iconSize = 20,
  disabled,
  inheritColor,
  className,
}: {
  icon: string
  label: string
  onClick: () => void
  /** sm = 36px (azioni di riga), md = 40px (barre e dialog). */
  size?: 'sm' | 'md'
  iconSize?: number
  disabled?: boolean
  /** Prende il colore del contenitore invece di on-surface-variant. */
  inheritColor?: boolean
  className?: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      disabled={disabled}
      className={clsx(
        'state flex items-center justify-center rounded-pill',
        size === 'sm' ? 'h-9 w-9' : 'h-10 w-10',
        !inheritColor && 'text-on-surface-variant',
        className,
      )}
    >
      <Icon name={icon} size={iconSize} />
    </button>
  )
}

/* -------------------------------------------------------------- avatar -- */

/**
 * Toni degli avatar senza colore: container M3 con il suo testo, scelti dal
 * nome, cosi' ogni persona ha sempre lo stesso colore. Classi letterali per Tailwind.
 */
const AVATAR_TONES = [
  'bg-primary-container text-on-primary-container',
  'bg-tertiary-container text-on-tertiary-container',
  'bg-success-container text-on-success-container',
  'bg-secondary-container text-on-secondary-container',
] as const

function avatarTone(name: string): string {
  let hash = 0
  for (const char of name.toLowerCase()) hash = (hash * 31 + char.charCodeAt(0)) | 0
  return AVATAR_TONES[Math.abs(hash) % AVATAR_TONES.length]
}

export function Avatar({
  name,
  size = 32,
  color,
  ring,
}: {
  name: string
  size?: number
  color?: string
  ring?: boolean
}) {
  return (
    <span
      className={clsx(
        'inline-flex shrink-0 items-center justify-center rounded-pill font-medium',
        color ? 'text-white' : avatarTone(name),
      )}
      style={{
        width: size,
        height: size,
        background: color,
        fontSize: Math.max(10, Math.round(size * 0.36)),
        boxShadow: ring ? '0 0 0 2px var(--surface)' : undefined,
      }}
      title={name}
    >
      {initials(name)}
    </span>
  )
}

export function AvatarStack({
  people,
  size = 36,
  className,
}: {
  people: { name: string; color?: string }[]
  size?: number
  className?: string
}) {
  return (
    <div className={clsx('flex', className)} style={{ paddingLeft: 10 }}>
      {people.map((person, index) => (
        <span key={index} style={{ marginLeft: -10 }}>
          <Avatar name={person.name} color={person.color} size={size} ring={index > 0} />
        </span>
      ))}
    </div>
  )
}

/* ---------------------------------------------------------------- chip -- */

export function Chip({
  label,
  icon,
  trailingIcon,
  selected,
  variant = 'outlined',
  onClick,
  className,
  children,
}: {
  label?: string
  icon?: string
  trailingIcon?: string
  selected?: boolean
  variant?: 'outlined' | 'assist' | 'selected'
  onClick?: () => void
  className?: string
  children?: ReactNode
}) {
  const resolved = selected ? 'selected' : variant
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={clsx(
        resolved === 'selected' && 'chip-selected',
        resolved === 'outlined' && 'chip-outlined',
        resolved === 'assist' && 'chip-assist',
        className,
      )}
    >
      {icon && <Icon name={icon} size={18} />}
      {children ?? <span className="truncate">{label}</span>}
      {trailingIcon && <Icon name={trailingIcon} size={18} />}
    </button>
  )
}

/* -------------------------------------------------------------- campi --- */

export function Field({
  label,
  error,
  hint,
  children,
  className,
}: {
  label: string
  error?: string
  hint?: string
  children: ReactNode
  className?: string
}) {
  return (
    <div className={className}>
      <label className="field block cursor-text">
        <span className="field-label">{label}</span>
        {children}
      </label>
      {hint && !error && (
        <p className="mt-1 px-4 text-body-small text-on-surface-variant">{hint}</p>
      )}
      {error && <p className="mt-1 px-4 text-body-small text-error">{error}</p>}
    </div>
  )
}

/** Input password con l'occhio per mostrarla: va dentro un `Field`. */
export function PasswordInput({
  value,
  onChange,
  autoComplete,
  required,
}: {
  value: string
  onChange: (value: string) => void
  autoComplete: 'current-password' | 'new-password'
  required?: boolean
}) {
  const [visible, setVisible] = useState(false)
  return (
    <div className="flex items-center gap-2">
      <input
        className="field-input min-w-0 flex-1"
        type={visible ? 'text' : 'password'}
        autoComplete={autoComplete}
        autoCapitalize="none"
        autoCorrect="off"
        spellCheck={false}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        required={required}
      />
      <IconButton
        icon={visible ? 'visibility_off' : 'visibility'}
        label={visible ? gettext('Nascondi password') : gettext('Mostra password')}
        onClick={() => setVisible((current) => !current)}
        className="-my-2 -mr-2 shrink-0"
      />
    </div>
  )
}

/** Segmented button M3 (es. Spesa / Entrata). */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  className,
}: {
  value: T
  options: { value: T; label: string }[]
  onChange: (value: T) => void
  className?: string
}) {
  return (
    <div className={clsx('inline-flex rounded-pill bg-surface-container p-1', className)}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          aria-pressed={value === option.value}
          className={clsx(
            'state rounded-pill px-4 py-2 text-body-medium font-medium transition',
            value === option.value
              ? 'bg-surface text-on-surface shadow-fab'
              : 'text-on-surface-variant',
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

/** Switch M3 52×32 con thumb 26px. */
export function Switch({
  checked,
  onChange,
  label,
  disabled = false,
}: {
  checked: boolean
  onChange: (checked: boolean) => void
  label: string
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className="relative shrink-0 rounded-pill transition-colors duration-200 ease-m3 disabled:opacity-40"
      style={{
        width: 52,
        height: 32,
        background: checked ? 'var(--primary)' : 'var(--outline-variant)',
      }}
    >
      <span
        className="absolute rounded-pill bg-white transition-all duration-200 ease-m3"
        style={{ width: 26, height: 26, top: 3, left: checked ? 23 : 3 }}
      />
    </button>
  )
}

/* -------------------------------------------------------- feedback ------ */

/**
 * Pill di stato: tonale quando tutto torna, warning quando no. Con `href`
 * diventa un link (più grande, con freccia) che porta al dettaglio.
 */
export function StatusPill({
  ok,
  icon,
  href,
  children,
}: {
  ok: boolean
  icon?: string
  href?: string
  children: ReactNode
}) {
  const tone = ok
    ? 'bg-secondary-container text-on-secondary-container'
    : 'bg-warning-container text-on-warning-container'
  if (href) {
    return (
      <a
        href={href}
        className={clsx(
          'state inline-flex w-fit items-center gap-2 rounded-pill py-2 pl-4 pr-3 text-body-medium',
          tone,
        )}
      >
        <Icon name={icon ?? 'balance'} size={20} />
        {children}
        {!ok && <Icon name="chevron_right" size={20} />}
      </a>
    )
  }
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-pill px-3 py-1.5 text-body-medium font-medium',
        tone,
      )}
    >
      <Icon name={icon ?? (ok ? 'check_circle' : 'balance')} size={18} />
      {children}
    </span>
  )
}

export function Skeleton({ className, style }: { className?: string; style?: CSSProperties }) {
  return <div className={clsx('skeleton', className)} style={style} aria-hidden />
}

export function RowsSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="grid gap-1">
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton key={index} className="h-[72px]" />
      ))}
    </div>
  )
}

export function ErrorBanner({ error }: { error: unknown }) {
  if (!error) return null
  const message = error instanceof Error ? error.message : String(error)
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-row bg-error-container px-4 py-3 text-body-medium text-on-error-container"
    >
      <Icon name="error" size={20} />
      <span>{message}</span>
    </div>
  )
}

export function EmptyState({
  icon = 'inbox',
  illustration,
  title,
  description,
  action,
}: {
  icon?: string
  /** Un disegno (components/illustrations) al posto dell'icona nel cerchio. */
  illustration?: ReactNode
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="card-m3 flex flex-col items-center gap-2 px-6 py-10 text-center">
      {illustration ? (
        <div className="mb-2">{illustration}</div>
      ) : (
        <span className="mb-2 flex h-[72px] w-[72px] items-center justify-center rounded-pill bg-primary-container text-on-primary-container">
          <Icon name={icon} size={36} />
        </span>
      )}
      <p className="text-title-medium">{title}</p>
      {description && (
        <p className="max-w-md text-body-medium text-on-surface-variant">{description}</p>
      )}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}

/** Linear progress M3 determinato. */
export function Progress({ value, max, label }: { value: number; max: number; label: string }) {
  const percent = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0
  return (
    <div
      className="progress"
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={value}
    >
      <span style={{ width: `${percent}%` }} />
    </div>
  )
}

/* ----------------------------------------------------------- overlay ---- */

/**
 * Dialog centrato su desktop, bottom sheet su mobile: nel design sono la stessa
 * superficie con due ancoraggi diversi.
 */
export function Modal({
  open,
  onClose,
  title,
  children,
  wide,
  headerRight,
}: {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  wide?: boolean
  headerRight?: ReactNode
}) {
  useCloseOnEscape(open, onClose)
  useEffect(() => {
    if (!open) return
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = ''
    }
  }, [open])

  if (!open) return null
  return (
    // z-60: sopra il "+" del mobile (z-50), che altrimenti copre il fondo del form.
    // In basso con mt-auto e non con items-end: con items-end un form piu' alto
    // dello schermo usciva dall'alto e la sua parte iniziale non si raggiungeva.
    <div
      className="fixed inset-0 z-[60] flex items-start justify-center overflow-y-auto sm:p-6"
      style={{ background: 'var(--scrim)' }}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={clsx(
          'w-full bg-surface shadow-sheet',
          'mt-auto rounded-t-panel sm:my-auto sm:rounded-panel',
          wide ? 'sm:max-w-[620px]' : 'sm:max-w-[520px]',
        )}
        style={{ animation: 'none' }}
      >
        <div className="flex items-center gap-3 px-6 pb-2 pt-6 sm:px-7 sm:pt-7">
          <IconButton
            icon="close"
            label={gettext('Chiudi')}
            onClick={onClose}
            size="md"
            iconSize={22}
            className="-ml-2"
          />
          <h2 className="flex-1 text-[22px] font-semibold leading-7">{title}</h2>
          {headerRight}
        </div>
        <div className="px-6 pb-6 sm:px-7 sm:pb-7">{children}</div>
      </div>
    </div>
  )
}

/** Bottom sheet: su desktop diventa un pannello ancorato in basso a destra. */
export function BottomSheet({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
}) {
  return (
    <Modal open={open} onClose={onClose} title={title}>
      {children}
    </Modal>
  )
}

/* --------------------------------------------------------------- FAB ---- */

/**
 * FAB esteso M3: su mobile sta sopra la barra di navigazione, su desktop in
 * basso a destra. Ogni pagina mette il suo (es. "Nuovo").
 */
export function Fab({
  icon,
  label,
  onClick,
}: {
  icon: string
  label: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="state fixed bottom-[104px] right-4 z-50 flex h-14 items-center gap-3 rounded-fab bg-primary-container pl-4 pr-5 text-body-large font-medium text-on-primary-container shadow-fab-mobile md:bottom-8 md:right-8 md:shadow-fab"
    >
      <Icon name={icon} size={24} />
      {label}
    </button>
  )
}

/* ------------------------------------------------------------ stepper --- */

/** Numero piccolo con − e + (sedute di sport, persone in casa). */
export function Stepper({
  value,
  onChange,
  min,
  max,
  label,
  format,
}: {
  value: number
  onChange: (value: number) => void
  min: number
  max: number
  label: string
  /** Testo al posto del numero (es. "Mai" per zero). */
  format?: (value: number) => string
}) {
  return (
    <div className="flex items-center gap-3" role="group" aria-label={label}>
      <IconButton
        icon="remove"
        size="md"
        label={gettext('Meno')}
        onClick={() => onChange(Math.max(min, value - 1))}
        disabled={value <= min}
        className="bg-surface-container-high disabled:opacity-40"
      />
      <span className="min-w-[4.5rem] text-center text-title-medium" aria-live="polite">
        {format ? format(value) : value}
      </span>
      <IconButton
        icon="add"
        size="md"
        label={gettext('Più')}
        onClick={() => onChange(Math.min(max, value + 1))}
        disabled={value >= max}
        className="bg-surface-container-high disabled:opacity-40"
      />
    </div>
  )
}

/* -------------------------------------------------------- chip editor --- */

/**
 * Elenco di voci libere come chip: si tolgono con la x, si aggiungono
 * scrivendo (Invio) o toccando uno spunto. Le voci gia' presenti spariscono
 * dagli spunti, senza badare alle maiuscole.
 */
export function ChipEditor({
  items,
  onAdd,
  onRemove,
  suggestions = [],
  inputLabel,
  disabled,
}: {
  items: { key: string; label: string }[]
  onAdd: (label: string) => void
  onRemove: (key: string) => void
  suggestions?: string[]
  inputLabel: string
  disabled?: boolean
}) {
  const [text, setText] = useState('')
  const present = new Set(items.map((item) => item.label.toLowerCase()))
  const open = suggestions.filter((suggestion) => !present.has(suggestion.toLowerCase()))

  const add = (raw: string) => {
    const label = raw.replace(/\s+/g, ' ').trim()
    if (!label || present.has(label.toLowerCase())) return
    onAdd(label)
  }
  const submit = () => {
    add(text)
    setText('')
  }

  return (
    <div className="grid gap-3">
      {items.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {items.map((item) => (
            <Chip
              key={item.key}
              selected
              label={item.label}
              trailingIcon="close"
              onClick={() => onRemove(item.key)}
            />
          ))}
        </div>
      )}
      {/* Niente <form>: l'editor sta spesso dentro il form di una sezione. */}
      <div className="flex items-end gap-2">
        <Field label={inputLabel} className="min-w-0 flex-1">
          <input
            className="field-input"
            value={text}
            maxLength={80}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={(event) => {
              if (event.key !== 'Enter') return
              event.preventDefault()
              submit()
            }}
            disabled={disabled}
          />
        </Field>
        <button
          type="button"
          className="btn-tonal mb-0.5 px-4"
          disabled={disabled || !text.trim()}
          onClick={submit}
        >
          <Icon name="add" size={20} />
          {gettext('Aggiungi')}
        </button>
      </div>
      {open.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {open.map((suggestion) => (
            <Chip key={suggestion} icon="add" label={suggestion} onClick={() => add(suggestion)} />
          ))}
        </div>
      )}
    </div>
  )
}
