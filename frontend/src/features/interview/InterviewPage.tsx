// Intervista per il profilo (ADR 0013): una chiacchierata scritta o a voce al
// posto del wizard. Ogni turno passa da un job; quello che l'assistente capisce
// si accumula qui come proposta e va nel profilo solo con "Salva nel profilo".

import clsx from 'clsx'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import {
  useAddPreference,
  useCompleteOnboarding,
  useInterviewTurn,
  useJob,
  useProfile,
  useUpdateProfile,
} from '../../api/hooks'
import type { InterviewMessage } from '../../api/hooks'
import { FoodPattern } from '../../components/illustrations'
import { Chip, ErrorBanner, Icon, IconButton, Skeleton, Switch } from '../../components/ui'
import { gettext, getLanguage, interpolate } from '../../lib/i18n'
import { formatSeconds, useRecorder } from '../../lib/recorder'
import type { PreferenceKind, ProfileDraft } from '../../lib/types'
import { ACTIVITY_OPTIONS, GOAL_OPTIONS, MEAL_OPTIONS, SEX_OPTIONS } from '../profile/options'

type Proposal = { kind: PreferenceKind; label: string; allergen: string }

const KIND_LABELS: Record<PreferenceKind, string> = {
  allergy: gettext('Allergia'),
  intolerance: gettext('Intolleranza'),
  like: gettext('Mi piace'),
  dislike: gettext('Non mi piace'),
}

/** Una riga leggibile per ogni campo proposto. */
function describe(key: string, value: unknown): string {
  switch (key) {
    case 'sex':
      return SEX_OPTIONS.find((option) => option.value === value)?.label ?? String(value)
    case 'height_cm':
      return interpolate(gettext('Altezza %s cm'), [String(value)])
    case 'weight_kg':
      return interpolate(gettext('Peso %s kg'), [String(value)])
    case 'goals':
      return (value as string[])
        .map((goal) => GOAL_OPTIONS.find((option) => option.value === goal)?.label ?? goal)
        .join(', ')
    case 'goals_note':
      return interpolate(gettext('Obiettivo: “%s”'), [String(value)])
    case 'activity_level':
      return interpolate(gettext('Attività: %s'), [
        ACTIVITY_OPTIONS.find((option) => option.value === value)?.label ?? String(value),
      ])
    case 'sport_sessions_per_week':
      return interpolate(gettext('Sport %s volte a settimana'), [String(value)])
    case 'conditions':
      return interpolate(gettext('Da considerare: %s'), [(value as string[]).join(', ')])
    case 'followed_by_nutritionist':
      return value ? gettext('Ti segue un nutrizionista') : gettext('Nessun nutrizionista')
    case 'meal_slots':
      return interpolate(gettext('Pasti: %s'), [
        (value as string[])
          .map((slot) => MEAL_OPTIONS.find((option) => option.value === slot)?.label ?? slot)
          .join(', '),
      ])
    case 'household_size':
      return interpolate(gettext('Cucini per %s'), [String(value)])
    default:
      return String(value)
  }
}

function speak(text: string) {
  if (!('speechSynthesis' in window)) return
  window.speechSynthesis.cancel()
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = getLanguage() === 'en' ? 'en-GB' : 'it-IT'
  window.speechSynthesis.speak(utterance)
}

export function InterviewPage() {
  const { data: profile } = useProfile()
  if (!profile) return <Skeleton className="m-6 h-72 rounded-card" />
  return <Interview onboarding={!profile.onboarding_completed} />
}

function Interview({ onboarding }: { onboarding: boolean }) {
  const navigate = useNavigate()
  const turn = useInterviewTurn()
  const update = useUpdateProfile()
  const addPreference = useAddPreference()
  const complete = useCompleteOnboarding()
  const [messages, setMessages] = useState<InterviewMessage[]>(() => [
    {
      role: 'assistant',
      text: gettext(
        'Ciao! Ti faccio qualche domanda per conoscerti e proporti cosa mangiare. Puoi scrivere o parlare. Per cominciare: hai allergie o intolleranze alimentari?',
      ),
    },
  ])
  const [text, setText] = useState('')
  const [jobId, setJobId] = useState<string>()
  const [voice, setVoice] = useState(false)
  const [updates, setUpdates] = useState<Partial<ProfileDraft>>({})
  const [preferences, setPreferences] = useState<Proposal[]>([])
  const [finished, setFinished] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<unknown>(null)
  const { data: job } = useJob(jobId)
  const handled = useRef<string>()
  const bottom = useRef<HTMLDivElement>(null)
  const thinking = turn.isPending || job?.status === 'queued' || job?.status === 'running'

  const send = async (history: InterviewMessage[], audio?: File) => {
    setMessages(history)
    try {
      const started = await turn.mutateAsync({ messages: history, audio })
      setJobId(started.id)
    } catch {
      // Errore in fondo.
    }
  }

  const recorder = useRecorder((file) => {
    setVoice(true)
    void send([...messages, { role: 'user', text: '🎤 …' }], file)
  })

  // Turno pronto: la risposta in chat, le proposte nel riepilogo.
  useEffect(() => {
    if (!job || job.status !== 'ready' || handled.current === job.id) return
    handled.current = job.id
    const result = job.result
    setMessages((current) => {
      const next = [...current]
      const last = next[next.length - 1]
      if (result.heard && last?.role === 'user' && last.text === '🎤 …') {
        next[next.length - 1] = { role: 'user', text: result.heard }
      }
      return [...next, { role: 'assistant', text: result.reply ?? '' }]
    })
    setUpdates((current) => ({ ...current, ...(result.updates ?? {}) }))
    setPreferences((current) => {
      const merged = [...current]
      for (const item of result.preferences ?? []) {
        const exists = merged.some(
          (other) =>
            other.kind === item.kind && other.label.toLowerCase() === item.label.toLowerCase(),
        )
        if (!exists) merged.push(item)
      }
      return merged
    })
    if (result.done) setFinished(true)
    if (voice && result.reply) speak(result.reply)
  }, [job, voice])

  // Una risposta vocale non capita: la riga "🎤 …" diventa un invito a riprovare.
  useEffect(() => {
    if (job?.status === 'failed') {
      setMessages((current) =>
        current[current.length - 1]?.text === '🎤 …' ? current.slice(0, -1) : current,
      )
    }
  }, [job?.status])

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages.length, thinking, finished])

  const proposals = Object.entries(updates)
  const count = proposals.length + preferences.length

  const save = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      if (proposals.length) await update.mutateAsync(updates)
      for (const item of preferences) {
        await addPreference.mutateAsync({
          kind: item.kind,
          label: item.label,
          allergen: item.allergen || undefined,
        })
      }
      if (onboarding) {
        await complete.mutateAsync()
        navigate('/', { replace: true })
      } else {
        navigate('/profilo', { replace: true })
      }
    } catch (error) {
      setSaveError(error)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex min-h-dvh flex-col bg-surface-container-low">
      <header className="relative overflow-hidden bg-primary text-on-primary">
        <FoodPattern tone="dark" opacity={0.3} />
        <div className="relative mx-auto flex max-w-2xl items-center gap-3 px-4 py-3">
          <IconButton
            icon="arrow_back"
            size="md"
            inheritColor
            label={gettext('Indietro')}
            onClick={() => navigate(onboarding ? '/benvenuto' : '/profilo')}
          />
          <div className="min-w-0 flex-1">
            <h1 className="text-title-medium">{gettext('Due chiacchiere')}</h1>
            <p className="truncate text-body-small opacity-90">
              {gettext('Rispondi a voce o per iscritto: alla fine controlli tutto')}
            </p>
          </div>
          <label className="flex items-center gap-2 text-body-small">
            <Icon name="volume_up" size={18} />
            <Switch
              label={gettext('Leggi le risposte ad alta voce')}
              checked={voice}
              onChange={setVoice}
            />
          </label>
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-3 px-4 py-4">
        {messages.map((message, index) => (
          <div
            key={index}
            className={clsx(
              'max-w-[85%] whitespace-pre-line rounded-[20px] px-4 py-2.5 text-body-large',
              message.role === 'assistant'
                ? 'self-start rounded-bl-[6px] bg-surface text-on-surface shadow-sm'
                : 'self-end rounded-br-[6px] bg-primary text-on-primary',
            )}
          >
            {message.text}
          </div>
        ))}
        {thinking && (
          <div className="flex items-center gap-1.5 self-start rounded-[20px] rounded-bl-[6px] bg-surface px-4 py-3 shadow-sm">
            {[0, 1, 2].map((dot) => (
              <span
                key={dot}
                className="h-2 w-2 animate-pulse rounded-pill bg-on-surface-variant"
                style={{ animationDelay: `${dot * 200}ms` }}
              />
            ))}
          </div>
        )}
        <ErrorBanner error={turn.error ?? (job?.status === 'failed' ? job.error : null)} />

        {(count > 0 || finished) && (
          <section
            className={clsx(
              'mt-2 grid gap-3 rounded-card p-4',
              finished ? 'bg-primary-container text-on-primary-container' : 'bg-surface',
            )}
          >
            <h2 className="flex items-center gap-2 text-title-small">
              <Icon name="fact_check" size={20} />
              {finished ? gettext('Ecco cosa ho capito: controlla e salva') : gettext('Ho capito')}
            </h2>
            {count === 0 ? (
              <p className="text-body-medium">{gettext('Niente di nuovo da salvare.')}</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {proposals.map(([key, value]) => (
                  <Chip
                    key={key}
                    label={describe(key, value)}
                    trailingIcon="close"
                    onClick={() =>
                      setUpdates((current) => {
                        const next = { ...current }
                        delete next[key as keyof ProfileDraft]
                        return next
                      })
                    }
                  />
                ))}
                {preferences.map((item) => (
                  <Chip
                    key={`${item.kind}-${item.label}`}
                    icon={
                      item.kind === 'allergy' || item.kind === 'intolerance'
                        ? 'health_and_safety'
                        : item.kind === 'like'
                          ? 'favorite'
                          : 'thumb_down'
                    }
                    label={`${KIND_LABELS[item.kind]}: ${item.label}`}
                    trailingIcon="close"
                    onClick={() =>
                      setPreferences((current) => current.filter((other) => other !== item))
                    }
                  />
                ))}
              </div>
            )}
            <ErrorBanner error={saveError} />
            <div className="flex flex-wrap justify-end gap-2">
              {!finished && (
                <button type="button" className="btn-text" onClick={() => setFinished(true)}>
                  {gettext('Basta così')}
                </button>
              )}
              <button
                type="button"
                className="btn-filled"
                disabled={saving || (count === 0 && !onboarding)}
                onClick={save}
              >
                <Icon name="check" size={20} />
                {onboarding ? gettext('Salva e inizia') : gettext('Salva nel profilo')}
              </button>
            </div>
          </section>
        )}
        <div ref={bottom} />
      </main>

      {!finished && (
        <footer className="sticky bottom-0 border-t border-outline-variant bg-surface">
          <form
            className="mx-auto flex max-w-2xl items-end gap-2 px-4 py-3"
            onSubmit={(event) => {
              event.preventDefault()
              const value = text.trim()
              if (!value || thinking) return
              setText('')
              void send([...messages, { role: 'user', text: value }])
            }}
          >
            {recorder.recording ? (
              <div className="flex min-h-[48px] flex-1 items-center gap-3 rounded-pill bg-error-container px-4 text-on-error-container">
                <span className="h-3 w-3 animate-pulse rounded-pill bg-error" />
                <span className="flex-1 text-body-large">
                  {interpolate(gettext('Ti ascolto… %s'), [formatSeconds(recorder.seconds)])}
                </span>
              </div>
            ) : (
              <textarea
                className="field-input max-h-40 min-h-[48px] flex-1 resize-none rounded-[24px] bg-surface-container-high px-4 py-3"
                rows={1}
                maxLength={1000}
                placeholder={gettext('Scrivi la tua risposta')}
                value={text}
                disabled={thinking}
                onChange={(event) => setText(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault()
                    event.currentTarget.form?.requestSubmit()
                  }
                }}
              />
            )}
            {recorder.supported && (
              <IconButton
                icon={recorder.recording ? 'stop' : 'mic'}
                size="md"
                label={recorder.recording ? gettext('Ferma e invia') : gettext('Rispondi a voce')}
                disabled={thinking}
                onClick={() => (recorder.recording ? recorder.stop() : recorder.start())}
                className={clsx(
                  recorder.recording
                    ? 'bg-error text-white'
                    : 'bg-primary-container text-on-primary-container',
                )}
              />
            )}
            {!recorder.recording && (
              <IconButton
                icon="send"
                size="md"
                label={gettext('Invia')}
                disabled={thinking || !text.trim()}
                onClick={() => {
                  const value = text.trim()
                  if (!value) return
                  setText('')
                  void send([...messages, { role: 'user', text: value }])
                }}
                className="bg-primary text-on-primary disabled:opacity-40"
              />
            )}
          </form>
          {recorder.error && (
            <p className="mx-auto max-w-2xl px-4 pb-3 text-body-small text-error">
              {recorder.error}
            </p>
          )}
        </footer>
      )}
    </div>
  )
}
