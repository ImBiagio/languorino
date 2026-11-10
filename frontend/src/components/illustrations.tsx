// Illustrazioni del tema (ADR 0003): disegnate in SVG con i toni delle palette
// Material (--illo-* in index.css), cosi' cambiano insieme al tema e restano
// nitide a ogni dimensione. Sono decorative: niente testo, aria-hidden.

import { useId } from 'react'

type Tone = 'light' | 'dark'

/** Colori dei doodle: su fondo chiaro toni pieni, su fondo blu toni chiari. */
const TONES: Record<Tone, { line: string; warm: string; green: string; soft: string }> = {
  light: {
    line: 'var(--illo-blue-70)',
    warm: 'var(--illo-orange-70)',
    green: 'var(--illo-green-70)',
    soft: 'var(--illo-blue-90)',
  },
  dark: {
    line: 'var(--illo-blue-70)',
    warm: 'var(--illo-orange-70)',
    green: 'var(--illo-green-70)',
    soft: 'var(--illo-blue-50)',
  },
}

/**
 * Un doodle da 24×24: tratti arrotondati, come le Material Symbols, ma
 * colorati. `x`, `y` e `rotate` lo piazzano nella tessera del motivo.
 */
function Doodle({
  kind,
  x,
  y,
  rotate = 0,
  colors,
}: {
  kind: 'carrot' | 'leaf' | 'fork' | 'spoon' | 'citrus' | 'cherry' | 'cup' | 'wheat'
  x: number
  y: number
  rotate?: number
  colors: (typeof TONES)[Tone]
}) {
  const stroke = {
    fill: 'none',
    strokeWidth: 2,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
  }
  return (
    <g transform={`translate(${x} ${y}) rotate(${rotate} 12 12)`}>
      {kind === 'carrot' && (
        <>
          <path d="M6 20 17 9.5a3 3 0 0 0-4.5-4.5L4 16z" fill={colors.warm} />
          <path d="M15 7c1-2.5 3-3.5 5-3M16 8c2.5-.5 4 .3 5 2" {...stroke} stroke={colors.green} />
        </>
      )}
      {kind === 'leaf' && (
        <>
          <path d="M5 19C4 10 10 4 20 4c0 10-6 16-15 15z" fill={colors.green} />
          <path d="M5 19 14 10" {...stroke} stroke={colors.soft} />
        </>
      )}
      {kind === 'fork' && (
        <path d="M8 3v6a4 4 0 0 0 8 0V3M12 3v18" {...stroke} stroke={colors.line} />
      )}
      {kind === 'spoon' && (
        <>
          <ellipse cx="12" cy="7" rx="4" ry="5" fill={colors.line} />
          <path d="M12 12v9" {...stroke} stroke={colors.line} />
        </>
      )}
      {kind === 'citrus' && (
        <>
          <circle cx="12" cy="12" r="8" fill={colors.warm} />
          <path d="M12 6v12M6.8 9l10.4 6M6.8 15l10.4-6" {...stroke} stroke={colors.soft} />
        </>
      )}
      {kind === 'cherry' && (
        <>
          <path d="M8 15c1-5 3-9 7-11M16 15c0-4-.5-8-1-11" {...stroke} stroke={colors.green} />
          <circle cx="7.5" cy="17" r="3.5" fill={colors.warm} />
          <circle cx="16.5" cy="17" r="3.5" fill={colors.warm} />
        </>
      )}
      {kind === 'cup' && (
        <>
          <path d="M5 9h11v5a5 5 0 0 1-5 5h-1a5 5 0 0 1-5-5z" fill={colors.line} />
          <path
            d="M16 10h1.5a2.5 2.5 0 0 1 0 5H16M9 3c-1 1 1 2 0 3.5M12.5 3c-1 1 1 2 0 3.5"
            {...stroke}
            stroke={colors.line}
          />
        </>
      )}
      {kind === 'wheat' && (
        <path
          d="M12 21V5M12 9c-2.5-.5-3.5-2-3.5-4 2.5.5 3.5 2 3.5 4zm0 0c2.5-.5 3.5-2 3.5-4-2.5.5-3.5 2-3.5 4zm0 5c-2.5-.5-3.5-2-3.5-4 2.5.5 3.5 2 3.5 4zm0 0c2.5-.5 3.5-2 3.5-4-2.5.5-3.5 2-3.5 4z"
          {...stroke}
          stroke={colors.line}
        />
      )}
    </g>
  )
}

/**
 * Motivo di doodle del cibo che si ripete: per testate e fasce decorative.
 * Riempie il contenitore (posizione assoluta), quindi va dentro un
 * elemento `relative overflow-hidden` con il suo colore di fondo.
 */
export function FoodPattern({
  tone = 'light',
  opacity = 1,
  className,
}: {
  tone?: Tone
  opacity?: number
  className?: string
}) {
  const id = useId()
  const colors = TONES[tone]
  return (
    <svg
      aria-hidden
      className={className ?? 'pointer-events-none absolute inset-0 h-full w-full'}
      style={{ opacity }}
    >
      <defs>
        <pattern id={id} width="168" height="120" patternUnits="userSpaceOnUse">
          <Doodle kind="carrot" x={8} y={10} rotate={-10} colors={colors} />
          <Doodle kind="fork" x={62} y={6} rotate={18} colors={colors} />
          <Doodle kind="citrus" x={112} y={16} colors={colors} />
          <Doodle kind="leaf" x={36} y={66} rotate={8} colors={colors} />
          <Doodle kind="cherry" x={90} y={70} rotate={-12} colors={colors} />
          <Doodle kind="spoon" x={140} y={72} rotate={-24} colors={colors} />
          <Doodle kind="wheat" x={2} y={86} rotate={14} colors={colors} />
          <Doodle kind="cup" x={128} y={-2} rotate={10} colors={colors} />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill={`url(#${id})`} />
    </svg>
  )
}

/**
 * Un piatto apparecchiato visto dall'alto, con coltello, forchetta e un po'
 * di vapore: per gli stati vuoti del piano ("ancora niente da mangiare").
 */
export function EmptyPlateIllustration({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 220 140"
      className={className ?? 'h-32 w-auto'}
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {/* tovaglietta */}
      <rect x="22" y="22" width="176" height="104" rx="26" fill="var(--illo-blue-95)" />
      {/* piatto */}
      <circle cx="110" cy="74" r="40" fill="#ffffff" />
      <circle cx="110" cy="74" r="40" stroke="var(--illo-blue-90)" strokeWidth="3" />
      <circle
        cx="110"
        cy="74"
        r="28"
        stroke="var(--illo-blue-90)"
        strokeWidth="2"
        strokeDasharray="2 6"
      />
      {/* forchetta */}
      <path d="M50 46v14a6 6 0 0 0 12 0V46M56 46v58" stroke="var(--illo-blue-50)" strokeWidth="4" />
      {/* coltello */}
      <path d="M166 104V46c7 4 10 14 10 26h-10" stroke="var(--illo-blue-50)" strokeWidth="4" />
      {/* vapore */}
      <path
        d="M98 30c-4-4 4-7 0-12M110 26c-4-4 4-7 0-12M122 30c-4-4 4-7 0-12"
        stroke="var(--illo-blue-70)"
        strokeWidth="3.5"
      />
      {/* briciole di colore */}
      <circle cx="186" cy="34" r="5" fill="var(--illo-orange-70)" />
      <circle cx="34" cy="116" r="4" fill="var(--illo-green-70)" />
      <path d="M180 120c4-6 10-8 16-6-2 6-8 9-16 6z" fill="var(--illo-green-70)" />
    </svg>
  )
}
