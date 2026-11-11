// Conversazione a voce in tempo reale con Gemini Live (ADR 0014): il browser
// parla direttamente con Gemini con un token monouso preso dal backend, che ha
// gia' deciso modello, istruzioni e strumenti. Le trascrizioni compaiono man
// mano; quello che Gemini "segna" passa dal backend e va nel riepilogo.

import { GoogleGenAI, Modality } from '@google/genai'
import type { LiveServerMessage, Session } from '@google/genai'
import clsx from 'clsx'
import { useEffect, useRef, useState } from 'react'

import { cleanLiveCall, useStartLiveInterview } from '../../api/hooks'
import { ErrorBanner, Icon, IconButton } from '../../components/ui'
import { gettext } from '../../lib/i18n'
import { MicStream, VoicePlayer } from '../../lib/liveAudio'
import type { Proposals } from './proposals'

type Line = { role: 'assistant' | 'user'; text: string; open: boolean }
type Phase = 'idle' | 'connecting' | 'live' | 'ended'

export function canTalkLive(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof window.AudioContext !== 'undefined' &&
    typeof window.WebSocket !== 'undefined' &&
    Boolean(navigator.mediaDevices?.getUserMedia)
  )
}

export function LiveInterview({ proposals }: { proposals: Proposals }) {
  const start = useStartLiveInterview()
  const [phase, setPhase] = useState<Phase>('idle')
  const [speaking, setSpeaking] = useState(false)
  const [muted, setMuted] = useState(false)
  const [lines, setLines] = useState<Line[]>([])
  const [error, setError] = useState('')
  const session = useRef<Session | null>(null)
  const mic = useRef<MicStream | null>(null)
  const player = useRef<VoicePlayer | null>(null)
  const ending = useRef(false)
  const bottom = useRef<HTMLDivElement>(null)

  /** Aggiunge un pezzo di trascrizione alla riga aperta di quel ruolo. */
  const transcribe = (role: Line['role'], text: string) =>
    setLines((current) => {
      const next = current.map((line) =>
        line.role !== role && line.open ? { ...line, open: false } : line,
      )
      const last = next[next.length - 1]
      if (last && last.role === role && last.open) {
        next[next.length - 1] = { ...last, text: last.text + text }
        return next
      }
      return [...next, { role, text: text.trimStart(), open: true }]
    })

  const stop = () => {
    mic.current?.stop()
    mic.current = null
    session.current?.close()
    session.current = null
    player.current?.close()
    player.current = null
    setSpeaking(false)
    setLines((current) => current.map((line) => ({ ...line, open: false })))
    setPhase((current) => (current === 'idle' ? current : 'ended'))
  }

  const onMessage = async (message: LiveServerMessage) => {
    const content = message.serverContent
    for (const part of content?.modelTurn?.parts ?? []) {
      if (part.inlineData?.data) player.current?.play(part.inlineData.data)
    }
    if (content?.interrupted) player.current?.interrupt()
    if (content?.inputTranscription?.text) transcribe('user', content.inputTranscription.text)
    if (content?.outputTranscription?.text)
      transcribe('assistant', content.outputTranscription.text)
    if (content?.turnComplete) {
      setLines((current) => current.map((line) => ({ ...line, open: false })))
      // Ha salutato dopo fine_intervista: si chiude quando ha finito di parlare.
      if (ending.current) window.setTimeout(stop, 2500)
    }
    const calls = message.toolCall?.functionCalls ?? []
    if (!calls.length) return
    const responses = []
    for (const call of calls) {
      if (call.name === 'fine_intervista') {
        ending.current = true
        proposals.setFinished(true)
      } else if (call.name) {
        try {
          proposals.merge(await cleanLiveCall(call.name, call.args ?? {}))
        } catch {
          // Una proposta persa non ferma la conversazione.
        }
      }
      responses.push({ id: call.id, name: call.name, response: { ok: true } })
    }
    session.current?.sendToolResponse({ functionResponses: responses })
  }

  const begin = async () => {
    setError('')
    setPhase('connecting')
    ending.current = false
    try {
      const { token, model } = await start.mutateAsync()
      player.current = new VoicePlayer(setSpeaking)
      await player.current.resume()
      const ai = new GoogleGenAI({ apiKey: token, httpOptions: { apiVersion: 'v1alpha' } })
      session.current = await ai.live.connect({
        model,
        // Il resto (istruzioni, strumenti, trascrizioni) e' fissato nel token.
        config: { responseModalities: [Modality.AUDIO] },
        callbacks: {
          onmessage: (message) => void onMessage(message),
          onerror: () => setError(gettext('La conversazione si è interrotta. Riprova.')),
          onclose: () => {
            if (session.current) stop()
          },
        },
      })
      mic.current = new MicStream((data) =>
        session.current?.sendRealtimeInput({ audio: { data, mimeType: 'audio/pcm;rate=16000' } }),
      )
      await mic.current.start()
      setPhase('live')
      // Comincia lei: saluta e chiede di allergie e intolleranze.
      session.current.sendClientContent({
        turns: [{ role: 'user', parts: [{ text: gettext('Ciao, iniziamo.') }] }],
        turnComplete: true,
      })
    } catch (caught) {
      stop()
      setPhase('idle')
      setError(
        caught instanceof Error && caught.name === 'NotAllowedError'
          ? gettext('Non riesco a usare il microfono: controlla i permessi del browser.')
          : caught instanceof Error && caught.message
            ? caught.message
            : gettext('La conversazione non è partita. Riprova.'),
      )
    }
  }

  // Uscendo dalla pagina si chiude tutto: microfono, voce e sessione.
  useEffect(() => () => stop(), []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (mic.current) mic.current.muted = muted
  }, [muted])

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [lines.length])

  const live = phase === 'live'
  return (
    <div className="grid gap-4">
      <section className="grid justify-items-center gap-4 rounded-card bg-surface px-4 py-8 text-center">
        <button
          type="button"
          onClick={live ? stop : begin}
          disabled={phase === 'connecting'}
          aria-label={live ? gettext('Termina la conversazione') : gettext('Inizia a parlare')}
          className={clsx(
            'relative flex h-32 w-32 items-center justify-center rounded-pill text-white transition',
            live ? (speaking ? 'bg-tertiary' : 'bg-primary') : 'bg-primary',
            phase === 'connecting' && 'opacity-70',
          )}
        >
          {live && (
            <span
              className={clsx(
                'absolute inset-0 rounded-pill',
                speaking
                  ? 'animate-ping bg-tertiary opacity-40'
                  : !muted && 'animate-pulse bg-primary opacity-30',
              )}
            />
          )}
          <Icon
            name={
              live ? (speaking ? 'graphic_eq' : muted ? 'mic_off' : 'mic') : 'record_voice_over'
            }
            size={56}
            className="relative"
          />
        </button>
        <div>
          <p className="text-title-medium">
            {phase === 'connecting'
              ? gettext('Mi collego…')
              : live
                ? speaking
                  ? gettext('Sto parlando: puoi interrompermi')
                  : muted
                    ? gettext('Microfono spento')
                    : gettext('Ti ascolto')
                : phase === 'ended'
                  ? gettext('Conversazione finita')
                  : gettext('Parliamo a voce, come al telefono')}
          </p>
          <p className="mt-1 text-body-small text-on-surface-variant">
            {live
              ? gettext('Tocca il cerchio per finire. Quello che capisco compare nel riepilogo.')
              : gettext('Tocca il cerchio e rispondi a voce: ti faccio io le domande.')}
          </p>
        </div>
        {live && (
          <IconButton
            icon={muted ? 'mic_off' : 'mic'}
            size="md"
            label={muted ? gettext('Riaccendi il microfono') : gettext('Spegni il microfono')}
            onClick={() => setMuted(!muted)}
            className="bg-surface-container-high"
          />
        )}
        <ErrorBanner error={error || start.error} />
      </section>

      {lines.length > 0 && (
        <div className="flex flex-col gap-2">
          {lines.map((line, index) => (
            <div
              key={index}
              className={clsx(
                'max-w-[85%] rounded-[20px] px-4 py-2 text-body-medium',
                line.role === 'assistant'
                  ? 'self-start rounded-bl-[6px] bg-surface text-on-surface shadow-sm'
                  : 'self-end rounded-br-[6px] bg-primary text-on-primary',
                line.open && 'opacity-80',
              )}
            >
              {line.text}
            </div>
          ))}
          <div ref={bottom} />
        </div>
      )}
    </div>
  )
}
