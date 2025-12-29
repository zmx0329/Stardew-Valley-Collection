import { useAudioStore } from '../state/audio-store'

let audioContext: AudioContext | null = null
let audioReady = false

const isMuted = () => useAudioStore.getState().isMuted

const getAudioContext = () => {
  const AudioContextConstructor =
    window.AudioContext || (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext

  if (!AudioContextConstructor) {
    return null
  }

  if (!audioContext) {
    audioContext = new AudioContextConstructor()
  }

  return audioContext
}

export const ensureAudioContext = async () => {
  const context = getAudioContext()
  if (!context) {
    return null
  }

  if (context.state === 'suspended') {
    await context.resume()
  }

  audioReady = true
  return context
}

export const playGiftClick = () => {
  if (!audioReady || !audioContext || isMuted()) {
    return
  }
  const context = audioContext
  const now = context.currentTime

  const lowOsc = context.createOscillator()
  const lowGain = context.createGain()
  lowOsc.type = 'triangle'
  lowOsc.frequency.setValueAtTime(150, now)
  lowGain.gain.setValueAtTime(0.0001, now)
  lowGain.gain.exponentialRampToValueAtTime(0.2, now + 0.02)
  lowGain.gain.exponentialRampToValueAtTime(0.0001, now + 0.18)
  lowOsc.connect(lowGain)
  lowGain.connect(context.destination)
  lowOsc.start(now)
  lowOsc.stop(now + 0.2)

  const highOsc = context.createOscillator()
  const highGain = context.createGain()
  highOsc.type = 'square'
  highOsc.frequency.setValueAtTime(520, now + 0.02)
  highGain.gain.setValueAtTime(0.0001, now + 0.02)
  highGain.gain.exponentialRampToValueAtTime(0.14, now + 0.03)
  highGain.gain.exponentialRampToValueAtTime(0.0001, now + 0.14)
  highOsc.connect(highGain)
  highGain.connect(context.destination)
  highOsc.start(now + 0.02)
  highOsc.stop(now + 0.16)
}

export const playTypeBeep = () => {
  if (!audioReady || !audioContext || isMuted()) {
    return
  }
  const context = audioContext
  const now = context.currentTime
  const oscillator = context.createOscillator()
  const gain = context.createGain()

  oscillator.type = 'square'
  oscillator.frequency.setValueAtTime(720 + Math.random() * 120, now)
  gain.gain.setValueAtTime(0.0001, now)
  gain.gain.exponentialRampToValueAtTime(0.08, now + 0.01)
  gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.08)

  oscillator.connect(gain)
  gain.connect(context.destination)
  oscillator.start(now)
  oscillator.stop(now + 0.09)
}
