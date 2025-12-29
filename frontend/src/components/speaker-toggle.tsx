import { useAudioStore } from '../state/audio-store'

const SpeakerToggle = () => {
  const { isMuted, toggleMuted } = useAudioStore()
  const label = isMuted ? '取消静音' : '静音'

  return (
    <button className={`speaker-toggle ${isMuted ? 'muted' : ''}`} type="button" onClick={toggleMuted}>
      <span className="sr-only">{label}</span>
      <svg
        className="speaker-icon"
        viewBox="0 0 24 24"
        aria-hidden="true"
        focusable="false"
        role="img"
      >
        <path
          d="M4 9h4l5-4v14l-5-4H4z"
          fill="currentColor"
        />
        <path
          d="M16 8c1.5 1.2 2.4 2.7 2.4 4s-.9 2.8-2.4 4"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="square"
        />
        {isMuted && (
          <path
            d="M16 8l6 8M22 8l-6 8"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="square"
          />
        )}
      </svg>
    </button>
  )
}

export default SpeakerToggle
