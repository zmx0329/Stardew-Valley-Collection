import { useEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import { useAudioStore } from '../state/audio-store'

const BACKGROUND_MUSIC_SRC = encodeURI('/music/ConcernedApe - Stardew Valley Overture.mp3')

const BackgroundAudio = () => {
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const autoUnlockedRef = useRef(false)
  const location = useLocation()
  const { isMuted, pauseReason, clearPauseReason } = useAudioStore()

  const shouldPlay = pauseReason === null

  useEffect(() => {
    if (location.pathname !== '/' && pauseReason === 'cinematic') {
      clearPauseReason()
    }
  }, [clearPauseReason, location.pathname, pauseReason])

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) {
      return
    }
    if (shouldPlay) {
      audio.muted = isMuted || !autoUnlockedRef.current
      const playPromise = audio.play()
      if (playPromise) {
        playPromise
          .then(() => {
            if (autoUnlockedRef.current || isMuted) {
              return
            }
            autoUnlockedRef.current = true
            window.setTimeout(() => {
              const currentAudio = audioRef.current
              if (!currentAudio || useAudioStore.getState().isMuted) {
                return
              }
              currentAudio.muted = false
            }, 400)
          })
          .catch(() => {})
      }
    } else {
      audio.pause()
    }
  }, [isMuted, shouldPlay])

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) {
      return () => {}
    }
    const resumeOnMove = () => {
      if (!shouldPlay || isMuted || autoUnlockedRef.current) {
        return
      }
      audio.muted = false
      audio
        .play()
        .then(() => {
          autoUnlockedRef.current = true
        })
        .catch(() => {})
    }
    document.addEventListener('pointermove', resumeOnMove, { capture: true })
    return () => {
      document.removeEventListener('pointermove', resumeOnMove, { capture: true })
    }
  }, [isMuted, shouldPlay])

  return <audio ref={audioRef} src={BACKGROUND_MUSIC_SRC} preload="auto" loop autoPlay playsInline />
}

export default BackgroundAudio
