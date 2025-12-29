import { useEffect } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import CapturePage from './pages/Capture'
import CollectionPage from './pages/Collection'
import HomePage from './pages/Home'
import IntroPage from './pages/intro-page'
import BackgroundAudio from './components/background-audio'
import SpeakerToggle from './components/speaker-toggle'
import { useAudioStore } from './state/audio-store'
import { ensureAudioContext, playGiftClick } from './utils/sfx'
import './App.css'

const App = () => {
  const { isMuted } = useAudioStore()

  useEffect(() => {
    const shouldPlayClick = (eventTarget: EventTarget | null) => {
      if (!(eventTarget instanceof Element)) {
        return false
      }
      const clickable = eventTarget.closest('button, a, [role="button"]')
      if (!clickable) {
        return false
      }
      if (clickable instanceof HTMLButtonElement && clickable.disabled) {
        return false
      }
      if (clickable.getAttribute('aria-disabled') === 'true') {
        return false
      }
      return true
    }

    const handleClick = (event: MouseEvent) => {
      if (!shouldPlayClick(event.target) || isMuted) {
        return
      }
      ensureAudioContext()
        .then(() => playGiftClick())
        .catch(() => {})
    }

    document.addEventListener('click', handleClick, { capture: true })
    return () => {
      document.removeEventListener('click', handleClick, { capture: true })
    }
  }, [isMuted])

  return (
    <BrowserRouter>
      <div className="app-shell">
        <BackgroundAudio />
        <SpeakerToggle />
        <Routes>
          <Route path="/" element={<IntroPage />} />
          <Route path="/home" element={<HomePage />} />
          <Route path="/capture" element={<CapturePage />} />
          <Route path="/collection" element={<CollectionPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}

export default App
