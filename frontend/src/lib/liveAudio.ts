// Audio per la conversazione in tempo reale con Gemini Live (ADR 0014): il
// microfono va mandato a pezzetti come PCM 16 bit mono a 16 kHz, la voce
// arriva come PCM 16 bit mono a 24 kHz e va suonata in fila, senza buchi.

const IN_RATE = 16000
const OUT_RATE = 24000

function toBase64(bytes: Uint8Array): string {
  let binary = ''
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
  }
  return btoa(binary)
}

function fromBase64(data: string): Int16Array {
  const binary = atob(data)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  return new Int16Array(bytes.buffer, 0, Math.floor(bytes.length / 2))
}

/** Il microfono a pezzi di circa 250 ms, gia' in PCM 16 kHz base64. */
export class MicStream {
  private stream?: MediaStream
  private context?: AudioContext
  private source?: MediaStreamAudioSourceNode
  private processor?: ScriptProcessorNode
  muted = false

  constructor(private onChunk: (base64: string) => void) {}

  async start() {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    })
    this.context = new AudioContext()
    await this.context.resume()
    this.source = this.context.createMediaStreamSource(this.stream)
    this.processor = this.context.createScriptProcessor(4096, 1, 1)
    const ratio = this.context.sampleRate / IN_RATE
    this.processor.onaudioprocess = (event) => {
      if (this.muted) return
      const input = event.inputBuffer.getChannelData(0)
      const out = new Int16Array(Math.floor(input.length / ratio))
      for (let i = 0; i < out.length; i++) {
        const start = Math.floor(i * ratio)
        const end = Math.min(input.length, Math.floor((i + 1) * ratio))
        let sum = 0
        for (let j = start; j < end; j++) sum += input[j]
        const value = Math.max(-1, Math.min(1, sum / Math.max(1, end - start)))
        out[i] = value < 0 ? value * 0x8000 : value * 0x7fff
      }
      this.onChunk(toBase64(new Uint8Array(out.buffer)))
    }
    this.source.connect(this.processor)
    // Collegato all'uscita solo perche' Chrome lo faccia girare: esce silenzio.
    this.processor.connect(this.context.destination)
  }

  stop() {
    this.processor?.disconnect()
    this.source?.disconnect()
    this.stream?.getTracks().forEach((track) => track.stop())
    void this.context?.close()
    this.processor = undefined
  }
}

/** La voce di Gemini, un pezzo dopo l'altro; ``interrupt`` la zittisce subito. */
export class VoicePlayer {
  private context = new AudioContext({ sampleRate: OUT_RATE })
  private next = 0
  private playing = new Set<AudioBufferSourceNode>()

  constructor(private onSpeaking: (speaking: boolean) => void) {}

  async resume() {
    await this.context.resume()
  }

  play(base64: string) {
    const samples = fromBase64(base64)
    if (!samples.length) return
    const buffer = this.context.createBuffer(1, samples.length, OUT_RATE)
    const channel = buffer.getChannelData(0)
    for (let i = 0; i < samples.length; i++) channel[i] = samples[i] / 0x8000
    const source = this.context.createBufferSource()
    source.buffer = buffer
    source.connect(this.context.destination)
    this.next = Math.max(this.next, this.context.currentTime + 0.02)
    source.start(this.next)
    this.next += buffer.duration
    this.playing.add(source)
    this.onSpeaking(true)
    source.onended = () => {
      this.playing.delete(source)
      if (!this.playing.size) this.onSpeaking(false)
    }
  }

  interrupt() {
    for (const source of this.playing) {
      try {
        source.stop()
      } catch {
        // Gia' finito.
      }
    }
    this.playing.clear()
    this.next = 0
    this.onSpeaking(false)
  }

  close() {
    this.interrupt()
    void this.context.close()
  }
}
