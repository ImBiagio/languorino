// Registrazione dal microfono (intervista e ricette a voce, ADR 0013).
//
// Si registra in WAV mono a 16 kHz, codificato qui: il WebM/Opus di
// MediaRecorder (Chrome) Gemini non lo capisce ("non ho sentito bene"), il WAV
// si'. 16 kHz bastano per la voce: un minuto pesa circa 2 MB.

import { useCallback, useEffect, useRef, useState } from 'react'

import { gettext } from './i18n'

const RATE = 16000
/** Oltre si ferma da sola: il backend accetta 10 MB, circa 5 minuti. */
const MAX_SECONDS = 290

export function canRecord(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof window.AudioContext !== 'undefined' &&
    Boolean(navigator.mediaDevices?.getUserMedia)
  )
}

/** I campioni del microfono ridotti a 16 kHz (media sui blocchi). */
function downsample(chunks: Float32Array[], from: number): Int16Array {
  const length = chunks.reduce((total, chunk) => total + chunk.length, 0)
  const merged = new Float32Array(length)
  let offset = 0
  for (const chunk of chunks) {
    merged.set(chunk, offset)
    offset += chunk.length
  }
  const ratio = from / RATE
  const out = new Int16Array(Math.floor(length / ratio))
  for (let i = 0; i < out.length; i++) {
    const start = Math.floor(i * ratio)
    const end = Math.min(length, Math.floor((i + 1) * ratio))
    let sum = 0
    for (let j = start; j < end; j++) sum += merged[j]
    const value = Math.max(-1, Math.min(1, sum / Math.max(1, end - start)))
    out[i] = value < 0 ? value * 0x8000 : value * 0x7fff
  }
  return out
}

function wav(samples: Int16Array): Blob {
  const header = new DataView(new ArrayBuffer(44))
  const text = (at: number, value: string) =>
    [...value].forEach((char, index) => header.setUint8(at + index, char.charCodeAt(0)))
  text(0, 'RIFF')
  header.setUint32(4, 36 + samples.length * 2, true)
  text(8, 'WAVE')
  text(12, 'fmt ')
  header.setUint32(16, 16, true)
  header.setUint16(20, 1, true) // PCM
  header.setUint16(22, 1, true) // mono
  header.setUint32(24, RATE, true)
  header.setUint32(28, RATE * 2, true)
  header.setUint16(32, 2, true)
  header.setUint16(34, 16, true)
  text(36, 'data')
  header.setUint32(40, samples.length * 2, true)
  return new Blob([header, samples.buffer as ArrayBuffer], { type: 'audio/wav' })
}

type Session = {
  stream: MediaStream
  context: AudioContext
  source: MediaStreamAudioSourceNode
  processor: ScriptProcessorNode
  chunks: Float32Array[]
}

export function useRecorder(onDone: (file: File) => void) {
  const [recording, setRecording] = useState(false)
  const [seconds, setSeconds] = useState(0)
  const [error, setError] = useState('')
  const session = useRef<Session | null>(null)
  const timer = useRef<number>()
  const done = useRef(onDone)
  done.current = onDone

  const release = useCallback((): Session | null => {
    window.clearInterval(timer.current)
    const current = session.current
    session.current = null
    if (current) {
      current.processor.disconnect()
      current.source.disconnect()
      current.stream.getTracks().forEach((track) => track.stop())
      void current.context.close()
    }
    setRecording(false)
    return current
  }, [])

  const stop = useCallback(() => {
    const finished = release()
    if (!finished || !finished.chunks.length) return
    const samples = downsample(finished.chunks, finished.context.sampleRate)
    // Meno di mezzo secondo: un tocco per sbaglio, non una risposta.
    if (samples.length < RATE / 2) return
    done.current(new File([wav(samples)], 'voce.wav', { type: 'audio/wav' }))
  }, [release])

  const start = useCallback(async () => {
    setError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const context = new AudioContext()
      await context.resume()
      const source = context.createMediaStreamSource(stream)
      const processor = context.createScriptProcessor(4096, 1, 1)
      const chunks: Float32Array[] = []
      processor.onaudioprocess = (event) => {
        chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)))
      }
      source.connect(processor)
      // Collegato all'uscita solo perche' Chrome lo faccia girare: esce silenzio.
      processor.connect(context.destination)
      session.current = { stream, context, source, processor, chunks }
      setSeconds(0)
      setRecording(true)
      timer.current = window.setInterval(() => {
        setSeconds((value) => {
          if (value + 1 >= MAX_SECONDS) window.setTimeout(stop)
          return value + 1
        })
      }, 1000)
    } catch {
      release()
      setError(gettext('Non riesco a usare il microfono: controlla i permessi del browser.'))
    }
  }, [release, stop])

  // Uscendo dalla pagina si spegne il microfono.
  useEffect(() => () => void release(), [release])

  return { recording, seconds, error, start, stop, supported: canRecord() }
}

export function formatSeconds(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}
