import { create } from 'zustand'
import { createStore, type StateCreator } from 'zustand/vanilla'

export type NormalizedBounds = {
  x: number
  y: number
  width: number
  height: number
}

export type DetectionBoxInput = {
  id: string
  bounds: NormalizedBounds
  label?: string
  confidence?: number
}

export type DetectionBox = DetectionBoxInput & {
  area: number
}

export type TimeState = {
  hour: number
  minute: number
  month: number
  day: number
}

export type LabelDraft = {
  name: string
  category: string
  description: string
  energy: number
  health: number
  time: TimeState
  timePosition: {
    xPercent: number
    yPercent: number
  }
  timeScale: number
  tagPosition: {
    xPercent: number
    yPercent: number
  }
  tagScale: number
}

export type SaveStatus = 'idle' | 'saving' | 'success' | 'error'

export interface CaptureState {
  uploadFile: File | null
  previewUrl: string | null
  detectionBoxes: DetectionBox[]
  selectedBoxId: string | null
  labelDrafts: Record<string, LabelDraft>
  saveStatus: SaveStatus
  setUpload: (file: File | null, previewUrl: string | null) => void
  setDetectionBoxes: (boxes: DetectionBoxInput[]) => void
  selectBox: (boxId: string) => void
  updateLabelDraft: (boxId: string, updates: Partial<LabelDraft>) => void
  setSaveStatus: (status: SaveStatus) => void
  resetCapture: () => void
}

const createDefaultTimeState = (): TimeState => ({
  hour: 8,
  minute: 20,
  month: 1,
  day: 1,
})

const createEmptyLabelDraft = (): LabelDraft => ({
  name: '',
  category: '',
  description: '',
  energy: 0,
  health: 0,
  time: createDefaultTimeState(),
  timePosition: {
    xPercent: 0.83,
    yPercent: 0.14,
  },
  timeScale: 0.6,
  tagPosition: {
    xPercent: 0.5,
    yPercent: 0.5,
  },
  tagScale: 0.7,
})

const computeArea = (bounds: NormalizedBounds) =>
  Math.max(0, bounds.width) * Math.max(0, bounds.height)

const normalizeBoxes = (boxes: DetectionBoxInput[]): DetectionBox[] =>
  boxes.map((box) => ({
    ...box,
    area: computeArea(box.bounds),
  }))

const getLargestBoxId = (boxes: DetectionBox[]): string | null => {
  if (boxes.length === 0) {
    return null
  }

  const largestBox = boxes.reduce((currentLargest, candidate) => {
    if (candidate.area === currentLargest.area) {
      return currentLargest
    }

    return candidate.area > currentLargest.area ? candidate : currentLargest
  })

  return largestBox.id
}

const baseState = (): Omit<
  CaptureState,
  | 'setUpload'
  | 'setDetectionBoxes'
  | 'selectBox'
  | 'updateLabelDraft'
  | 'setSaveStatus'
  | 'resetCapture'
> => ({
  uploadFile: null,
  previewUrl: null,
  detectionBoxes: [],
  selectedBoxId: null,
  labelDrafts: {},
  saveStatus: 'idle',
})

const captureStoreCreator: StateCreator<CaptureState> = (set, get) => ({
  ...baseState(),
  setUpload: (file, previewUrl) => set({ uploadFile: file, previewUrl }),
  setDetectionBoxes: (boxes) => {
    const normalizedBoxes = normalizeBoxes(boxes)
    const largestBoxId = getLargestBoxId(normalizedBoxes)
    const currentDrafts = get().labelDrafts
    const nextDrafts = normalizedBoxes.reduce<Record<string, LabelDraft>>(
      (drafts, box) => {
        drafts[box.id] = currentDrafts[box.id]
          ? { ...currentDrafts[box.id] }
          : createEmptyLabelDraft()
        return drafts
      },
      {},
    )

    set({
      detectionBoxes: normalizedBoxes,
      selectedBoxId: largestBoxId,
      labelDrafts: nextDrafts,
    })
  },
  selectBox: (boxId) =>
    set((state) => {
      if (!state.detectionBoxes.some((box) => box.id === boxId)) {
        return state
      }

      return { selectedBoxId: boxId }
    }),
  updateLabelDraft: (boxId, updates) =>
    set((state) => {
      const existingDraft = state.labelDrafts[boxId] ?? createEmptyLabelDraft()

      return {
        labelDrafts: {
          ...state.labelDrafts,
          [boxId]: { ...existingDraft, ...updates },
        },
      }
    }),
  setSaveStatus: (status) => set({ saveStatus: status }),
  resetCapture: () => set(baseState()),
})

export const createCaptureStore = () => createStore<CaptureState>(captureStoreCreator)
export const useCaptureStore = create<CaptureState>(captureStoreCreator)
