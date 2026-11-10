// Illustrazioni del tema (ADR 0003): disegnate in SVG con i toni delle palette
// Material (--illo-* in index.css), cosi' cambiano insieme al tema e restano
// nitide a ogni dimensione. Sono decorative: niente testo, aria-hidden.

import { useId } from 'react'

import { mediaUrl } from '../lib/api'

type Tone = 'light' | 'dark' | 'strong'

export type DoodleKind =
  | 'carrot'
  | 'leaf'
  | 'fork'
  | 'spoon'
  | 'citrus'
  | 'cherry'
  | 'cup'
  | 'wheat'
  | 'fish'
  | 'drumstick'
  | 'bread'
  | 'cheese'
  | 'snowflake'

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
  // Per i disegni grandi su un fondo tenue (le tessere delle ricette).
  strong: {
    line: 'var(--illo-blue-50)',
    warm: 'var(--illo-orange-60)',
    green: 'var(--illo-green-50)',
    soft: '#ffffff',
  },
}

/**
 * Un doodle da 24×24: tratti arrotondati, come le Material Symbols, ma
 * colorati. `x`, `y` e `rotate` lo piazzano nella tessera del motivo.
 */
export function Doodle({
  kind,
  x,
  y,
  rotate = 0,
  colors,
}: {
  kind: DoodleKind
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
      {kind === 'fish' && (
        <>
          <path d="M3 12c3-5 9-6 14-2l4-3v10l-4-3c-5 4-11 3-14-2z" fill={colors.line} />
          <circle cx="8" cy="11" r="1.2" fill={colors.soft} />
        </>
      )}
      {kind === 'drumstick' && (
        <>
          <path d="M13 3a7 7 0 0 1 5 12l-3 1-3 3-3-3 1-3A7 7 0 0 1 13 3z" fill={colors.warm} />
          <path d="M9 16 5 20" {...stroke} stroke={colors.line} strokeWidth={3} />
          <circle cx="4.5" cy="20.5" r="1.8" fill={colors.line} />
        </>
      )}
      {kind === 'bread' && (
        <>
          <path d="M4 12a8 6 0 0 1 16 0v6a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z" fill={colors.warm} />
          <path d="M8 10.5l2 3M12 10l2 3M16 10.5l1 2" {...stroke} stroke={colors.soft} />
        </>
      )}
      {kind === 'cheese' && (
        <>
          <path d="M3 17 19 7l2 2v10H3z" fill={colors.warm} />
          <circle cx="9" cy="15.5" r="1.4" fill={colors.soft} />
          <circle cx="15" cy="14" r="1.8" fill={colors.soft} />
          <circle cx="17.5" cy="17.5" r="1" fill={colors.soft} />
        </>
      )}
      {kind === 'snowflake' && (
        <path
          d="M12 3v18M4.2 7.5l15.6 9M4.2 16.5l15.6-9M9.5 4.5 12 7l2.5-2.5M9.5 19.5 12 17l2.5 2.5"
          {...stroke}
          stroke={colors.line}
        />
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

/* ---------------------------------------------------------- ricette ---- */

const RECIPE_ART: Record<string, { kind: DoodleKind; background: string }> = {
  produce: { kind: 'carrot', background: 'var(--success-container)' },
  meat: { kind: 'drumstick', background: 'var(--illo-orange-90)' },
  fish: { kind: 'fish', background: 'var(--illo-blue-90)' },
  dairy: { kind: 'cheese', background: 'var(--warning-container)' },
  bakery: { kind: 'bread', background: 'var(--warning-container)' },
  pantry: { kind: 'wheat', background: 'var(--illo-blue-95)' },
  spices: { kind: 'leaf', background: 'var(--success-container)' },
  frozen: { kind: 'snowflake', background: 'var(--illo-blue-90)' },
  drinks: { kind: 'cup', background: 'var(--tertiary-container)' },
  other: { kind: 'spoon', background: 'var(--surface-container-high)' },
}

/**
 * La "foto" di una ricetta che non ne ha una: il fondo e il disegno del suo
 * ingrediente principale, su una trama leggera di doodle.
 */
export function RecipeArt({
  category,
  size = 64,
  className,
}: {
  category: string
  /** Lato del disegno al centro, in px. */
  size?: number
  className?: string
}) {
  const art = RECIPE_ART[category] ?? RECIPE_ART.other
  return (
    <div
      aria-hidden
      className={className ?? 'relative h-full w-full overflow-hidden'}
      style={{ background: art.background }}
    >
      <FoodPattern opacity={0.22} />
      <svg
        viewBox="0 0 24 24"
        width={size}
        height={size}
        className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 drop-shadow-sm"
      >
        <Doodle kind={art.kind} x={0} y={0} colors={TONES.strong} />
      </svg>
    </div>
  )
}

/**
 * La copertina di una ricetta: la sua immagine (foto vera o disegnata
 * dall'AI, ADR 0011) se c'e', altrimenti il disegno della categoria.
 */
export function RecipeCover({
  recipe,
  size = 64,
  className,
}: {
  recipe: { image?: string | null; main_category: string }
  size?: number
  className?: string
}) {
  if (recipe.image) {
    return (
      <img
        src={mediaUrl(recipe.image)}
        alt=""
        loading="lazy"
        className={className ?? 'absolute inset-0 h-full w-full object-cover'}
      />
    )
  }
  return <RecipeArt category={recipe.main_category} size={size} className={className} />
}

/** Un ricettario aperto con qualche doodle sulle pagine: il ricettario vuoto. */
export function CookbookIllustration({ className }: { className?: string }) {
  return (
    <svg aria-hidden viewBox="0 0 220 140" className={className ?? 'h-32 w-auto'} fill="none">
      <ellipse cx="110" cy="124" rx="78" ry="8" fill="var(--illo-blue-95)" />
      {/* copertina */}
      <path d="M22 30h176v86a6 6 0 0 1-6 6H28a6 6 0 0 1-6-6z" fill="var(--illo-blue-50)" />
      {/* pagine */}
      <path d="M30 24c28-8 56-6 78 6v88c-22-12-50-14-78-6z" fill="#ffffff" />
      <path d="M190 24c-28-8-56-6-78 6v88c22-12 50-14 78-6z" fill="#ffffff" />
      <path d="M110 30v88" stroke="var(--illo-blue-90)" strokeWidth="3" />
      {/* righe di testo */}
      <g stroke="var(--illo-blue-90)" strokeWidth="3" strokeLinecap="round">
        <path d="M44 84h48M44 94h40M128 82h46M128 92h34M128 102h42" />
      </g>
      <g transform="translate(50 40) scale(1.6)">
        <Doodle kind="carrot" x={0} y={0} colors={TONES.strong} />
      </g>
      <g transform="translate(134 38) scale(1.5)">
        <Doodle kind="cherry" x={0} y={0} colors={TONES.strong} />
      </g>
      <circle cx="198" cy="22" r="5" fill="var(--illo-orange-70)" />
      <path d="M14 112c4-6 10-8 16-6-2 6-8 9-16 6z" fill="var(--illo-green-70)" />
    </svg>
  )
}
