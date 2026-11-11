// Chiedi a Languorino (ADR 0016): domande su profilo, piano e piano del
// nutrizionista ("quanta pasta tra pranzo e cena?"). Ogni domanda e' un job
// sul modello veloce; la chat legge soltanto, non cambia niente.

import clsx from 'clsx'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useAsk, useJob } from '../../api/hooks'
import type { InterviewMessage } from '../../api/hooks'
import { FoodPattern } from '../../components/illustrations'
import { ErrorBanner, IconButton } from '../../components/ui'
import { gettext } from '../../lib/i18n'

// La conversazione resta finche' la scheda e' aperta: uscire per guardare il
// piano e tornare non deve farla ripartire da capo.
const STORAGE_KEY = 'languorino.ask'

function loadMessages(): InterviewMessage[] {
  try {
    const saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY) ?? '[]') as unknown
    return Array.isArray(saved) ? (saved as InterviewMessage[]) : []
  } catch {
    return []
  }
}

function saveMessages(messages: InterviewMessage[]) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(messages))
  } catch {
    // Senza storage la chat funziona lo stesso, solo non sopravvive all'uscita.
  }
}

export function AskPage() {
  const navigate = useNavigate()
  const ask = useAsk()
  const [messages, setMessages] = useState<InterviewMessage[]>(loadMessages)
  const [text, setText] = useState('')
  const [jobId, setJobId] = useState<string>()
  const { data: job } = useJob(jobId)
  const handled = useRef<string>()
  const bottom = useRef<HTMLDivElement>(null)
  const thinking = ask.isPending || job?.status === 'queued' || job?.status === 'running'

  const suggestions = [
    gettext('Quanta pasta mangio oggi tra pranzo e cena?'),
    gettext('Cosa ceno domani?'),
    gettext('Cosa devo cucinare oggi per i prossimi giorni?'),
    gettext('Cosa dice il nutrizionista sui legumi?'),
  ]

  const send = async (question: string) => {
    const value = question.trim()
    if (!value || thinking) return
    const history: InterviewMessage[] = [...messages, { role: 'user', text: value }]
    setText('')
    setMessages(history)
    try {
      const started = await ask.mutateAsync(history)
      setJobId(started.id)
    } catch {
      // Errore in fondo.
    }
  }

  useEffect(() => {
    if (!job || job.status !== 'ready' || handled.current === job.id) return
    handled.current = job.id
    setMessages((current) => [...current, { role: 'assistant', text: job.result.reply ?? '' }])
  }, [job])

  useEffect(() => saveMessages(messages), [messages])

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages.length, thinking])

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
            onClick={() => navigate(-1)}
          />
          <div className="min-w-0 flex-1">
            <h1 className="text-title-medium">{gettext('Chiedi a Languorino')}</h1>
            <p className="truncate text-body-small opacity-90">
              {gettext('Risponde con il tuo profilo e il tuo piano')}
            </p>
          </div>
          {messages.length > 0 && (
            <IconButton
              icon="restart_alt"
              size="md"
              inheritColor
              label={gettext('Nuova conversazione')}
              disabled={thinking}
              onClick={() => {
                setMessages([])
                setJobId(undefined)
                ask.reset()
              }}
            />
          )}
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-3 px-4 py-4">
        <div className="max-w-[85%] self-start rounded-[20px] rounded-bl-[6px] bg-surface px-4 py-2.5 text-body-large text-on-surface shadow-sm">
          {gettext(
            'Chiedimi quello che vuoi sui tuoi pasti: grammature, cosa mangi o cucini e quando, cosa dice il piano del nutrizionista.',
          )}
        </div>
        {messages.length === 0 && (
          <div className="flex flex-wrap gap-2">
            {suggestions.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                className="state rounded-pill border border-outline-variant bg-surface px-4 py-2 text-left text-label-large text-on-surface"
                onClick={() => void send(suggestion)}
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}
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
        <ErrorBanner error={ask.error ?? (job?.status === 'failed' ? job.error : null)} />
        <div ref={bottom} />
      </main>

      <footer className="sticky bottom-0 border-t border-outline-variant bg-surface">
        <form
          className="safe-bottom mx-auto flex max-w-2xl items-end gap-2 px-4 py-3"
          onSubmit={(event) => {
            event.preventDefault()
            void send(text)
          }}
        >
          <textarea
            className="field-input max-h-40 min-h-[48px] flex-1 resize-none rounded-[24px] bg-surface-container-high px-4 py-3"
            rows={1}
            maxLength={1000}
            placeholder={gettext('Scrivi una domanda')}
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
          <IconButton
            icon="send"
            size="md"
            label={gettext('Invia')}
            disabled={thinking || !text.trim()}
            onClick={() => void send(text)}
            className="bg-primary text-on-primary disabled:opacity-40"
          />
        </form>
      </footer>
    </div>
  )
}
