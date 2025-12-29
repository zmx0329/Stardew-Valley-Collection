import { create } from 'zustand'

type PauseReason = 'cinematic' | null

type AudioState = {
  isMuted: boolean
  pauseReason: PauseReason
  toggleMuted: () => void
  setMuted: (value: boolean) => void
  pauseForCinematic: () => void
  clearPauseReason: () => void
}

export const useAudioStore = create<AudioState>((set) => ({
  isMuted: false,
  pauseReason: null,
  toggleMuted: () => set((state) => ({ isMuted: !state.isMuted })),
  setMuted: (value) => set({ isMuted: value }),
  pauseForCinematic: () => set({ pauseReason: 'cinematic' }),
  clearPauseReason: () => set({ pauseReason: null }),
}))
