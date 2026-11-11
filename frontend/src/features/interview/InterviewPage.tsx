// Intervista per il profilo: una conversazione a voce in tempo reale (ADR 0014)
// o una chat scritta, anche con messaggi vocali (ADR 0013), al posto del
// wizard. Quello che l'assistente capisce si accumula come proposta e va nel
// profilo solo con "Salva nel profilo".

import clsx from 'clsx'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useInterviewTurn, useJob, useProfile } from '../../api/hooks'
import type { InterviewMessage } from '../../api/hooks'
import { FoodPattern } from '../../components/illustrations'
import { ErrorBanner, Icon, IconButton, Skeleton, Switch } from '../../components/ui'
import { gettext, getLanguage, interpolate } from '../../lib/i18n'
import { formatSeconds, useRecorder } from '../../lib/recorder'
import { LiveInterview, canTalkLive } from './LiveInterview'
import { ProposalsPanel, useProposals } from './proposals'

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
  const proposals = useProposals(onboarding)
  const [mode, setMode] = useState<'live' | 'chat'>(() => (canTalkLive() ? 'live' : 'chat'))
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
    proposals.merge(result)
    if (result.done) proposals.setFinished(true)
    if (voice && result.reply) speak(result.reply)
  }, [job, voice]) // eslint-disable-line react-hooks/exhaustive-deps

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
  }, [messages.length, thinking, proposals.finished])

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
          {mode === 'chat' && (
            <label className="flex items-center gap-2 text-body-small">
              <Icon name="volume_up" size={18} />
              <Switch
                label={gettext('Leggi le risposte ad alta voce')}
                checked={voice}
                onChange={setVoice}
              />
            </label>
          )}
        </div>
        {canTalkLive() && (
          <div className="relative mx-auto flex max-w-2xl gap-2 px-4 pb-3" role="tablist">
            {(
              [
                ['live', 'record_voice_over', gettext('Parliamo')],
                ['chat', 'chat', gettext('Chat')],
              ] as const
            ).map(([value, icon, label]) => (
              <button
                key={value}
                type="button"
                role="tab"
                aria-selected={mode === value}
                onClick={() => setMode(value)}
                className={clsx(
                  'flex items-center gap-1.5 rounded-pill px-4 py-1.5 text-label-large transition',
                  mode === value ? 'bg-white text-primary' : 'text-on-primary opacity-90',
                )}
              >
                <Icon name={icon} size={18} />
                {label}
              </button>
            ))}
          </div>
        )}
      </header>

      <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-3 px-4 py-4">
        {mode === 'live' && <LiveInterview proposals={proposals} />}
        {mode === 'chat' &&
          messages.map((message, index) => (
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
        {mode === 'chat' && thinking && (
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

        <ProposalsPanel proposals={proposals} />
        <div ref={bottom} />
      </main>

      {mode === 'chat' && !proposals.finished && (
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
