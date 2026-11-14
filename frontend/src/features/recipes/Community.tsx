// Ricette viste dagli altri (ADR 0017): stelle da 1 a 5, commenti con
// risposte e foto, profilo pubblico `/u/<handle>` con le ricette pubbliche.

import { useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import {
  useAddComment,
  useDeleteComment,
  usePublicProfile,
  useRateRecipe,
  useRecipeComments,
} from '../../api/hooks'
import { useConfirm } from '../../components/ConfirmDialog'
import { FoodPattern, RecipeCover } from '../../components/illustrations'
import { Avatar, EmptyState, ErrorBanner, Icon, IconButton, Skeleton } from '../../components/ui'
import { mediaUrl } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { formatDate, formatDateTime } from '../../lib/format'
import { gettext, interpolate, ngettext } from '../../lib/i18n'
import type { RatingSummary, RecipeComment } from '../../lib/types'
import { formatMinutes } from './options'

const MAX_IMAGES = 3

/** Chi guarda, noto solo a sessione caricata (come per la pagina condivisa). */
export function useViewer(): string | undefined {
  const { user, ready } = useAuth()
  return ready ? (user ? String(user.id) : 'anon') : undefined
}

/* ------------------------------------------------------------ stelle ---- */

export function Stars({ value, size = 18 }: { value: number; size?: number }) {
  return (
    <span className="inline-flex text-tertiary" aria-hidden>
      {[1, 2, 3, 4, 5].map((star) => {
        // Mezza stella da 0,25 a 0,75 sopra l'intero: 3,4 → tre e mezza.
        const full = value >= star - 0.25
        const half = !full && value >= star - 0.75
        return (
          <Icon
            key={star}
            name={half ? 'star_half' : 'star'}
            size={size}
            filled={full || half}
            className={full || half ? '' : 'opacity-30'}
          />
        )
      })}
    </span>
  )
}

export function RatingLine({ rating }: { rating: Pick<RatingSummary, 'average' | 'count'> }) {
  if (!rating.count || rating.average === null) {
    return (
      <span className="text-body-medium text-on-surface-variant">
        {gettext('Ancora nessun voto')}
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-2 text-body-medium">
      <Stars value={rating.average} />
      <span className="amount font-medium">{rating.average.toFixed(1)}</span>
      <span className="text-on-surface-variant">
        {interpolate(ngettext('(%s voto)', '(%s voti)', rating.count), [rating.count])}
      </span>
    </span>
  )
}

/** Il voto di chi guarda: stelle da toccare, di nuovo la stessa per toglierlo. */
export function RateRecipe({ token, rating }: { token: string; rating: RatingSummary }) {
  const rate = useRateRecipe(token)
  const [hover, setHover] = useState(0)
  const mine = rating.mine ?? 0
  const shown = hover || mine

  return (
    <div className="grid gap-1">
      <div className="flex items-center gap-1" onMouseLeave={() => setHover(0)}>
        {[1, 2, 3, 4, 5].map((star) => (
          <button
            key={star}
            type="button"
            className="state rounded-pill p-1 text-tertiary"
            disabled={rate.isPending}
            aria-label={interpolate(ngettext('%s stella', '%s stelle', star), [star])}
            aria-pressed={mine === star}
            onMouseEnter={() => setHover(star)}
            onClick={() => rate.mutate(mine === star ? null : star)}
          >
            <Icon
              name="star"
              size={30}
              filled={shown >= star}
              className={shown >= star ? '' : 'opacity-40'}
            />
          </button>
        ))}
      </div>
      <p className="text-body-small text-on-surface-variant">
        {mine
          ? gettext('Il tuo voto. Tocca di nuovo la stessa stella per toglierlo.')
          : gettext('Tocca le stelle per votarla.')}
      </p>
      <ErrorBanner error={rate.error} />
    </div>
  )
}

/* ---------------------------------------------------------- commenti ---- */

export function CommentsSection({
  token,
  backTo,
}: {
  token: string
  /** Dove tornare dopo l'accesso, per chi non ha fatto login. */
  backTo: string
}) {
  const { user } = useAuth()
  const viewer = useViewer()
  const { data: comments, isPending, error } = useRecipeComments(token, viewer)
  const count = (comments ?? []).reduce(
    (total, item) => total + (item.is_deleted ? 0 : 1) + item.replies.length,
    0,
  )

  return (
    <section className="grid gap-4 rounded-card bg-surface-container-low p-5">
      <h2 className="text-title-medium">
        {comments
          ? interpolate(ngettext('%s commento', '%s commenti', count), [count])
          : gettext('Commenti')}
      </h2>
      {user ? (
        <CommentForm token={token} />
      ) : (
        <p className="text-body-medium text-on-surface-variant">
          <Link
            className="text-primary underline"
            to={`/accedi?next=${encodeURIComponent(backTo)}`}
          >
            {gettext('Accedi')}
          </Link>{' '}
          {gettext('per votare e commentare.')}
        </p>
      )}
      {isPending && <Skeleton className="h-20 rounded-row" />}
      <ErrorBanner error={error} />
      {comments && comments.length === 0 && (
        <p className="text-body-medium text-on-surface-variant">
          {gettext('Nessun commento: l’hai provata? Racconta com’è venuta.')}
        </p>
      )}
      <ul className="grid gap-4">
        {comments?.map((comment) => (
          <li key={comment.id} className="grid gap-3">
            <CommentItem token={token} comment={comment} canReply={Boolean(user)} />
            {comment.replies.length > 0 && (
              <ul className="ml-5 grid gap-3 border-l-2 border-outline-variant pl-4">
                {comment.replies.map((reply) => (
                  <li key={reply.id}>
                    <CommentItem token={token} comment={reply} canReply={false} />
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}

function CommentItem({
  token,
  comment,
  canReply,
}: {
  token: string
  comment: RecipeComment
  canReply: boolean
}) {
  const remove = useDeleteComment(token)
  const confirm = useConfirm()
  const [replying, setReplying] = useState(false)

  if (comment.is_deleted) {
    return (
      <p className="flex items-center gap-2 text-body-medium italic text-on-surface-variant">
        <Icon name="chat_bubble_outline" size={18} />
        {gettext('Commento eliminato')}
      </p>
    )
  }

  const author = comment.author!
  return (
    <article className="grid gap-2">
      <header className="flex items-center gap-2">
        <Avatar name={author.name} size={32} />
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-x-2 text-body-medium font-medium">
            {author.handle ? (
              <Link to={`/u/${author.handle}`} className="hover:underline">
                {author.name}
              </Link>
            ) : (
              author.name
            )}
            {author.is_recipe_author && (
              <span className="rounded-pill bg-primary-container px-2 py-0.5 text-label-small text-on-primary-container">
                {gettext('Autore')}
              </span>
            )}
            {comment.stars && <Stars value={comment.stars} size={14} />}
          </p>
          <p className="text-body-small text-on-surface-variant">
            {formatDateTime(comment.created_at)}
          </p>
        </div>
        {comment.can_delete && (
          <IconButton
            icon="delete"
            size="sm"
            label={gettext('Elimina il commento')}
            onClick={async () => {
              const ok = await confirm({
                title: gettext('Eliminare il commento?'),
                message: gettext('Spariscono anche le foto.'),
                confirmLabel: gettext('Elimina'),
                icon: 'delete',
                destructive: true,
              })
              if (ok) remove.mutate(comment.id)
            }}
          />
        )}
      </header>
      {comment.text && <p className="whitespace-pre-line text-body-large">{comment.text}</p>}
      {comment.images.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {comment.images.map((src) => (
            <a key={src} href={mediaUrl(src)} target="_blank" rel="noreferrer">
              <img
                src={mediaUrl(src)}
                alt=""
                loading="lazy"
                className="h-28 w-28 rounded-row object-cover"
              />
            </a>
          ))}
        </div>
      )}
      {canReply && !replying && (
        <button
          type="button"
          className="btn-text btn-sm -ml-3 w-fit"
          onClick={() => setReplying(true)}
        >
          <Icon name="reply" size={18} />
          {gettext('Rispondi')}
        </button>
      )}
      {replying && (
        <CommentForm token={token} parent={comment.id} onDone={() => setReplying(false)} />
      )}
      <ErrorBanner error={remove.error} />
    </article>
  )
}

function CommentForm({
  token,
  parent,
  onDone,
}: {
  token: string
  parent?: string
  onDone?: () => void
}) {
  const add = useAddComment(token)
  const [text, setText] = useState('')
  const [images, setImages] = useState<File[]>([])
  const input = useRef<HTMLInputElement>(null)

  return (
    <form
      className="grid gap-2"
      onSubmit={async (event) => {
        event.preventDefault()
        try {
          await add.mutateAsync({ text: text.trim(), parent, images })
          setText('')
          setImages([])
          onDone?.()
        } catch {
          // Errore sotto.
        }
      }}
    >
      <textarea
        className="field min-h-[72px] resize-y rounded-row bg-surface-container-high px-4 py-3 text-body-large outline-none"
        value={text}
        maxLength={2000}
        autoFocus={Boolean(parent)}
        placeholder={
          parent ? gettext('Scrivi una risposta…') : gettext('Com’è venuta? Un consiglio?')
        }
        aria-label={parent ? gettext('Risposta') : gettext('Commento')}
        onChange={(event) => setText(event.target.value)}
      />
      {images.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {images.map((file, index) => (
            <div key={`${file.name}-${index}`} className="relative">
              <img
                src={URL.createObjectURL(file)}
                alt=""
                className="h-20 w-20 rounded-row object-cover"
              />
              <button
                type="button"
                className="absolute -right-2 -top-2 rounded-pill bg-surface p-0.5 shadow-fab"
                aria-label={gettext('Togli la foto')}
                onClick={() => setImages(images.filter((_, other) => other !== index))}
              >
                <Icon name="close" size={16} />
              </button>
            </div>
          ))}
        </div>
      )}
      <input
        ref={input}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        multiple
        hidden
        onChange={(event) => {
          const picked = Array.from(event.target.files ?? [])
          setImages([...images, ...picked].slice(0, MAX_IMAGES))
          event.target.value = ''
        }}
      />
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          className="btn-text btn-sm"
          disabled={images.length >= MAX_IMAGES}
          onClick={() => input.current?.click()}
        >
          <Icon name="add_photo_alternate" size={18} />
          {gettext('Foto')}
        </button>
        <span className="flex-1" />
        {onDone && (
          <button type="button" className="btn-text btn-sm" onClick={onDone}>
            {gettext('Annulla')}
          </button>
        )}
        <button
          className="btn-filled btn-sm"
          disabled={add.isPending || (!text.trim() && images.length === 0)}
        >
          <Icon name="send" size={18} />
          {parent ? gettext('Rispondi') : gettext('Pubblica')}
        </button>
      </div>
      <ErrorBanner error={add.error} />
    </form>
  )
}

/* -------------------------------------------------- /u/:handle ---- */

export function PublicProfilePage() {
  const { handle } = useParams()
  const viewer = useViewer()
  const { data: profile, error, isPending } = usePublicProfile(handle, viewer)

  return (
    <div className="min-h-dvh bg-surface">
      <header className="relative overflow-hidden bg-primary text-on-primary">
        <FoodPattern tone="dark" opacity={0.3} />
        <div className="relative mx-auto flex max-w-4xl items-center gap-3 px-5 py-3">
          <Link to="/" className="flex items-center gap-2">
            <img src="/logo-mark.svg" alt="" width={32} height={32} className="h-8 w-8" />
            <span className="text-title-medium font-medium">Languorino</span>
          </Link>
        </div>
      </header>
      <main className="mx-auto grid max-w-4xl gap-5 px-5 pb-10 pt-6">
        {isPending && <Skeleton className="h-40 rounded-card" />}
        {error && (
          <EmptyState
            icon="person_off"
            title={gettext('Questo profilo non è pubblico')}
            description={gettext('Un profilo si vede solo quando ha almeno una ricetta pubblica.')}
          />
        )}
        {profile && (
          <>
            <header className="flex items-center gap-4">
              <Avatar name={profile.name} size={64} />
              <div className="min-w-0">
                <h1 className="text-[28px] font-medium leading-9">{profile.name}</h1>
                <p className="text-body-medium text-on-surface-variant">
                  {interpolate(
                    ngettext('%s ricetta pubblica', '%s ricette pubbliche', profile.recipes.length),
                    [profile.recipes.length],
                  )}
                  {' · '}
                  {interpolate(gettext('su Languorino dal %s'), [formatDate(profile.since)])}
                </p>
              </div>
            </header>
            {profile.is_me && (
              <p className="rounded-row bg-primary-container px-4 py-3 text-body-medium text-on-primary-container">
                {gettext(
                  'È il tuo profilo pubblico: lo vede chiunque. Ci sono solo le ricette che hai reso pubbliche.',
                )}
              </p>
            )}
            <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {profile.recipes.map((recipe) => (
                <li key={recipe.id}>
                  <Link
                    to={`/r/${recipe.share_token}`}
                    className="state block overflow-hidden rounded-card bg-surface-container-low"
                  >
                    <div className="relative h-40">
                      <RecipeCover recipe={recipe} size={64} />
                    </div>
                    <div className="grid gap-1 p-4">
                      <h2 className="text-title-medium">{recipe.title}</h2>
                      <p className="flex flex-wrap items-center gap-2 text-body-small text-on-surface-variant">
                        {recipe.total_minutes > 0 && (
                          <span>{formatMinutes(recipe.total_minutes)}</span>
                        )}
                        {recipe.rating_count > 0 && recipe.rating_average !== null && (
                          <span className="inline-flex items-center gap-1">
                            <Stars value={recipe.rating_average} size={14} />
                            {recipe.rating_average.toFixed(1)}
                          </span>
                        )}
                      </p>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </>
        )}
      </main>
    </div>
  )
}
