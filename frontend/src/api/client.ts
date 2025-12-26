const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8001'

type DetectResponse = {
  boxes: {
    id: string
    label?: string
    confidence?: number
    bounds: { x: number; y: number; width: number; height: number }
  }[]
  image_size: { width: number; height: number }
}

type TextResponse = { description: string }
type ImageResponse = { image_base64: string; source?: string; note?: string }
type LabelResponse = { label: string }

export type SaveArtworkPayload = {
  user_id: string
  base_image: string
  composed_image?: string
  label: {
    name: string
    category: string
    description: string
    energy: number
    health: number
    time: { hour: number; minute: number; month: number; day: number }
    tag_position: { x_percent: number; y_percent: number }
    tag_scale: number
  }
  box_bounds?: { x: number; y: number; width: number; height: number }
}

export type SaveArtworkResponse = {
  id: string
  url: string
  created_at: string
  checksum: string
}

export type ArtworkRecord = {
  id: string
  user_id: string
  url: string
  created_at: string
}

export type ArtworksResponse = {
  items: ArtworkRecord[]
  total?: number | null
}

const apiFetch = async <T>(path: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  })
  if (!response.ok) {
    let detail: unknown
    try {
      detail = await response.json()
    } catch {
      // ignore
    }
    const detailObj = detail && typeof detail === 'object' ? (detail as Record<string, unknown>) : undefined
    const inner = detailObj && typeof detailObj.detail === 'object' ? (detailObj.detail as Record<string, unknown>) : undefined
    const code = (inner?.code as string | number | undefined) ?? response.status
    const message = (inner?.message as string | undefined) ?? response.statusText
    throw new Error(`${code}: ${message}`)
  }
  return (await response.json()) as T
}

export const detectObjects = async (imageBase64: string, maxResults = 20) =>
  apiFetch<DetectResponse>('/detect', {
    method: 'POST',
    body: JSON.stringify({ image_base64: imageBase64, max_results: Math.min(maxResults, 20) }),
  })

export const generateDescription = async (objectName: string, category: string) =>
  apiFetch<TextResponse>('/generate-text', {
    method: 'POST',
    body: JSON.stringify({ object_name: objectName, category }),
  })

export const generateLabel = async (
  imageBase64: string,
  bounds: { x: number; y: number; width: number; height: number },
  hint?: string,
) =>
  apiFetch<LabelResponse>('/generate-label', {
    method: 'POST',
    body: JSON.stringify({ image_base64: imageBase64, bounds, hint }),
  })

export const generatePixelImage = async (imageBase64: string, prompt?: string) =>
  apiFetch<ImageResponse>('/generate-image', {
    method: 'POST',
    body: JSON.stringify({ image_base64: imageBase64, prompt, block_size: 10 }),
  })

export const saveArtwork = async (payload: SaveArtworkPayload) =>
  apiFetch<SaveArtworkResponse>('/save-artwork', { method: 'POST', body: JSON.stringify(payload) })

export const listArtworks = async (limit = 20, offset = 0) =>
  apiFetch<ArtworksResponse>(`/artworks?limit=${limit}&offset=${offset}`)
