import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
  type KeyboardEvent,
  type PointerEvent as ReactPointerEvent,
} from 'react'
import { Link } from 'react-router-dom'
import html2canvas from 'html2canvas'
import {
  useCaptureStore,
  type DetectionBoxInput,
  type LabelDraft,
} from '../state/capture-store'
import {
  detectObjects,
  generateDescription,
  generateLabel,
  generatePixelImage,
  saveArtwork,
  type SaveArtworkPayload,
} from '../api/client'

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))

const categoryOptions = ['菜品', '食物', '采集', '家具', '手工艺品', '杂物']
const namePool = ['暖黄色吊灯', '旧木箱', '陶罐', '青草茶', '野莓', '木椅', '罐装果酱']
const descriptionPool = [
  '带着太阳晒过的温热气息，闻起来像夏天的谷仓。',
  '边角有些磕碰，却让人想起旧日的集市。',
  '甜香绕着鼻尖打转，像刚出炉的面包。',
  '表面覆着微尘，仿佛等待被再次使用。',
  '轻轻摇晃能听到松散的谷粒声，像在低语。',
]

const PAGE_SIZE = 20

const fileToDataUrl = (file: Blob) =>
  new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        resolve(reader.result)
      } else {
        reject(new Error('无法读取文件'))
      }
    }
    reader.onerror = (error) => reject(error)
    reader.readAsDataURL(file)
  })

const defaultTime = (): LabelDraft['time'] => {
  const now = new Date()
  return {
    hour: now.getHours(),
    minute: now.getMinutes(),
    month: now.getMonth() + 1,
    day: now.getDate(),
  }
}

const buildInitialDraft = (box: DetectionBoxInput, index: number): LabelDraft => {
  const category = categoryOptions[index % categoryOptions.length]
  const x = clamp(box.bounds.x + box.bounds.width * 0.65, 0.16, 0.84)
  const y = clamp(box.bounds.y + box.bounds.height + 0.12, 0.22, 0.9)

  return {
    name: box.label || namePool[index % namePool.length],
    category,
    description: '',
    energy: 60 + Math.floor(Math.random() * 60),
    health: 40 + Math.floor(Math.random() * 60),
    time: defaultTime(),
    timePosition: { xPercent: 0.83, yPercent: 0.14 },
    timeScale: 1,
    tagPosition: { xPercent: x, yPercent: y },
    tagScale: 1,
  }
}

const clampLongEdge = (value: number) => {
  if (value < 720) return 720
  if (value > 1600) return 1600
  return 1280
}

const loadImageFromUrl = (url: string) =>
  new Promise<HTMLImageElement>((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = reject
    img.src = url
  })

const resizeImageToBounds = async (file: File) => {
  const tempUrl = URL.createObjectURL(file)
  const img = await loadImageFromUrl(tempUrl)
  URL.revokeObjectURL(tempUrl)

  const longEdge = Math.max(img.width, img.height)
  const targetLongEdge = clampLongEdge(longEdge)
  const scale = targetLongEdge / longEdge
  const targetWidth = Math.round(img.width * scale)
  const targetHeight = Math.round(img.height * scale)

  const canvas = document.createElement('canvas')
  canvas.width = targetWidth
  canvas.height = targetHeight
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('canvas unsupported')
  ctx.imageSmoothingEnabled = true
  ctx.drawImage(img, 0, 0, targetWidth, targetHeight)

  const blob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      (result) => {
        if (!result) {
          reject(new Error('无法生成预览'))
          return
        }
        resolve(result)
      },
      file.type || 'image/png',
      0.92,
    )
  })

  const resizedFile = new File([blob], file.name, { type: blob.type })
  const previewUrl = URL.createObjectURL(blob)
  return { file: resizedFile, url: previewUrl, width: targetWidth, height: targetHeight }
}

const pixelateFromUrl = async (url: string, blockSize = 10) => {
  const img = await loadImageFromUrl(url)
  const canvas = document.createElement('canvas')
  canvas.width = img.width
  canvas.height = img.height
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('canvas unsupported')
  ctx.imageSmoothingEnabled = false

  const smallW = Math.max(1, Math.round(img.width / blockSize))
  const smallH = Math.max(1, Math.round(img.height / blockSize))

  ctx.drawImage(img, 0, 0, smallW, smallH)

  const upCanvas = document.createElement('canvas')
  upCanvas.width = img.width
  upCanvas.height = img.height
  const upCtx = upCanvas.getContext('2d')
  if (!upCtx) throw new Error('canvas unsupported')
  upCtx.imageSmoothingEnabled = false
  upCtx.drawImage(canvas, 0, 0, smallW, smallH, 0, 0, img.width, img.height)

  return upCanvas.toDataURL('image/png')
}

const formatTime = (hour: number, minute: number) => {
  const suffix = hour < 12 ? '上午' : '下午'
  const displayHour = hour % 12 === 0 ? 12 : hour % 12
  const paddedMinute = minute.toString().padStart(2, '0')
  return `${suffix} ${displayHour}:${paddedMinute}`
}

const CapturePage = () => {
  const fileInputId = 'capture-upload-input'
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const previewRef = useRef<HTMLDivElement | null>(null)
  const tagRef = useRef<HTMLDivElement | null>(null)
  const timeRef = useRef<HTMLDivElement | null>(null)
  const previewUrlRef = useRef<string | null>(null)
  const pixelPreviewRef = useRef<string | null>(null)
  const taskRef = useRef(0)

  const [isDragging, setIsDragging] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [pixelPreviewUrl, setPixelPreviewUrl] = useState<string | null>(null)
  const [isGeneratingPixel, setIsGeneratingPixel] = useState(false)
  const [generationNote, setGenerationNote] = useState<string | null>(null)
  const [descriptionLoading, setDescriptionLoading] = useState(false)
  const [nameLoading, setNameLoading] = useState(false)
  const [resizeInfo, setResizeInfo] = useState<{ width: number; height: number } | null>(null)
  const [tagDragging, setTagDragging] = useState(false)
  const [detecting, setDetecting] = useState(false)
  const [saveMessage, setSaveMessage] = useState<string | null>(null)
  const [objectPage, setObjectPage] = useState(0)
  const [timeDragging, setTimeDragging] = useState(false)
  const describedRef = useRef<Set<string>>(new Set())

  const uploadFile = useCaptureStore((state) => state.uploadFile)
  const previewUrl = useCaptureStore((state) => state.previewUrl)
  const detectionBoxes = useCaptureStore((state) => state.detectionBoxes)
  const selectedBoxId = useCaptureStore((state) => state.selectedBoxId)
  const labelDrafts = useCaptureStore((state) => state.labelDrafts)
  const saveStatus = useCaptureStore((state) => state.saveStatus)
  const setUpload = useCaptureStore((state) => state.setUpload)
  const setDetectionBoxes = useCaptureStore((state) => state.setDetectionBoxes)
  const selectBox = useCaptureStore((state) => state.selectBox)
  const updateLabelDraft = useCaptureStore((state) => state.updateLabelDraft)
  const resetCapture = useCaptureStore((state) => state.resetCapture)
  const setSaveStatus = useCaptureStore((state) => state.setSaveStatus)

  const selectedDraft = useMemo(
    () => (selectedBoxId ? labelDrafts[selectedBoxId] : null),
    [labelDrafts, selectedBoxId],
  )

  useEffect(() => {
    if (previewUrlRef.current && previewUrlRef.current !== previewUrl && previewUrlRef.current.startsWith('blob:')) {
      URL.revokeObjectURL(previewUrlRef.current)
    }
    previewUrlRef.current = previewUrl
  }, [previewUrl])

  useEffect(() => {
    if (pixelPreviewRef.current && pixelPreviewRef.current !== pixelPreviewUrl && pixelPreviewRef.current.startsWith('blob:')) {
      URL.revokeObjectURL(pixelPreviewRef.current)
    }
    pixelPreviewRef.current = pixelPreviewUrl
  }, [pixelPreviewUrl])

  useEffect(() => {
    setObjectPage(0)
  }, [detectionBoxes.length])

  useEffect(() => {
    if (!selectedBoxId) return
    const index = detectionBoxes.findIndex((box) => box.id === selectedBoxId)
    if (index >= 0) {
      const targetPage = Math.floor(index / PAGE_SIZE)
      if (targetPage !== objectPage) {
        setObjectPage(targetPage)
      }
    }
  }, [detectionBoxes, objectPage, selectedBoxId])

  useEffect(() => {
    return () => {
      if (previewUrlRef.current && previewUrlRef.current.startsWith('blob:')) {
        URL.revokeObjectURL(previewUrlRef.current)
      }
      if (pixelPreviewRef.current && pixelPreviewRef.current.startsWith('blob:')) {
        URL.revokeObjectURL(pixelPreviewRef.current)
      }
    }
  }, [])

  const handleBrowseClick = () => {
    fileInputRef.current?.click()
  }

  const runPixelPreview = useCallback(
    async (imageBase64: string, taskId: number) => {
      setIsGeneratingPixel(true)
      setGenerationNote('正在生成像素风...')
      try {
        const result = await generatePixelImage(imageBase64)
        if (taskRef.current !== taskId) return
        setPixelPreviewUrl(result.image_base64)
        if (result.source === 'fallback') {
          setGenerationNote(result.note || '生图服务未生效，已使用本地像素化')
        } else {
          setGenerationNote(null)
        }
      } catch (error) {
        if (taskRef.current !== taskId) return
        const fallback = await pixelateFromUrl(imageBase64, 12)
        setPixelPreviewUrl(fallback)
        const message = error instanceof Error ? error.message.replace(/^Error:\s*/i, '') : String(error)
        setGenerationNote(`生图服务返回错误：${message || '已用本地像素化兜底'}`)
        console.error('生图生成失败，使用本地像素化回退', error)
      } finally {
        if (taskRef.current === taskId) {
          setIsGeneratingPixel(false)
        }
      }
    },
    [],
  )

  const acceptFile = useCallback(
    async (file: File | null) => {
      if (!file) return
      if (!file.type.startsWith('image/')) {
        setUploadError('只能上传图片文件，换一张试试吧')
        return
      }

      const newTaskId = taskRef.current + 1
      taskRef.current = newTaskId
      setGenerationNote('正在压缩尺寸并召唤像素风...')
      setUploadError(null)
      setPixelPreviewUrl(null)
      setResizeInfo(null)
      setSaveMessage(null)
      setDetecting(true)
      resetCapture()
      describedRef.current.clear()

      try {
        const resized = await resizeImageToBounds(file)
        if (taskRef.current !== newTaskId) return

        const dataUrl = await fileToDataUrl(resized.file)
        if (taskRef.current !== newTaskId) return

        setResizeInfo({ width: resized.width, height: resized.height })
        setUpload(resized.file, dataUrl)
        setSaveStatus('idle')

        const detectPromise = detectObjects(dataUrl, 20)
        const pixelPromise = runPixelPreview(dataUrl, newTaskId)

        const detectResult = await detectPromise
        if (taskRef.current !== newTaskId) return

        if (!detectResult.boxes.length) {
          setDetectionBoxes([])
          setUploadError('没看清…换张更清晰的照片试试？')
          return
        }

        setDetectionBoxes(
          detectResult.boxes.map((box) => ({
            id: box.id,
            label: box.label,
            confidence: box.confidence,
            bounds: box.bounds,
          })),
        )
        detectResult.boxes.forEach((box, index) => {
          updateLabelDraft(box.id, buildInitialDraft(box, index))
        })
        setObjectPage(0)
        await pixelPromise
      } catch (error) {
        if (taskRef.current === newTaskId) {
          setUploadError('处理图片时出了点小差，换一张试试吧')
          setDetectionBoxes([])
          setSaveStatus('idle')
          setGenerationNote(null)
          console.error('压缩或生成预览失败', error)
        }
      } finally {
        if (taskRef.current === newTaskId) {
          setDetecting(false)
        }
      }
    },
    [resetCapture, runPixelPreview, setDetectionBoxes, setSaveStatus, setUpload, updateLabelDraft],
  )

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null
    acceptFile(file)
    event.target.value = ''
  }

  const handleDragOver = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (event: DragEvent<HTMLDivElement>) => {
    if (event.relatedTarget && event.currentTarget.contains(event.relatedTarget as Node)) {
      return
    }
    setIsDragging(false)
  }

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setIsDragging(false)
    const file = event.dataTransfer.files?.[0] ?? null
    void acceptFile(file)
  }

  const handleEmptyKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      handleBrowseClick()
    }
  }

  const displayedPreview = pixelPreviewUrl ?? previewUrl

  const totalPages = Math.max(1, Math.ceil((detectionBoxes.length || 1) / PAGE_SIZE))
  const currentPage = Math.min(objectPage, totalPages - 1)
  const pagedBoxes = detectionBoxes.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE)
  const selectedBox = selectedBoxId ? detectionBoxes.find((box) => box.id === selectedBoxId) : null
  const displayedBoxes =
    selectedBox && !pagedBoxes.some((box) => box.id === selectedBoxId)
      ? [...pagedBoxes, selectedBox]
      : pagedBoxes

  const runDescriptionGeneration = async (name: string, category: string, boxId: string | null) => {
    setDescriptionLoading(true)
    try {
      const descriptor = await generateDescription(name || '这件物品', category || '杂物')
      if (boxId) {
        updateLabelDraft(boxId, { description: descriptor.description })
        describedRef.current.add(boxId)
      }
    } catch (error) {
      const fallback = descriptionPool[Math.floor(Math.random() * descriptionPool.length)]
      if (boxId) {
        updateLabelDraft(boxId, { description: fallback })
        describedRef.current.add(boxId)
      }
      console.error('文案生成失败，使用模板兜底', error)
    } finally {
      setDescriptionLoading(false)
    }
  }

  const handleNameSuggestion = async () => {
    if (!selectedBoxId || !selectedBox || !previewUrl || nameLoading) return
    setNameLoading(true)
    try {
      const result = await generateLabel(previewUrl, selectedBox.bounds, selectedBox.label)
      const nextName = result.label?.trim() || selectedDraft?.name || selectedBox.label || ''
      if (nextName) {
        updateLabelDraft(selectedBoxId, { name: nextName })
        await runDescriptionGeneration(nextName, selectedDraft?.category || '杂物', selectedBoxId)
      }
    } catch (error) {
      console.error('取名失败，保留原名', error)
    } finally {
      setNameLoading(false)
    }
  }

  const handleCategoryChange = (category: string) => {
    if (!selectedBoxId) return
    updateLabelDraft(selectedBoxId, { category })
  }

  const handleDescriptionGenerate = async () => {
    if (!selectedBoxId || !selectedDraft) return
    await runDescriptionGeneration(selectedDraft.name || '这件物品', selectedDraft.category || '杂物', selectedBoxId)
  }

  const handleStatChange = (field: 'energy' | 'health', value: number) => {
    if (!selectedBoxId) return
    const nextValue = clamp(Math.round(value), 0, 200)
    updateLabelDraft(selectedBoxId, { [field]: nextValue })
  }

  const adjustStat = (field: 'energy' | 'health', delta: number) => {
    if (!selectedBoxId) return
    const current = selectedDraft ? selectedDraft[field] : 0
    handleStatChange(field, current + delta)
  }

  const handleTimeChange = (field: 'hour' | 'minute' | 'month' | 'day', value: number) => {
    if (!selectedBoxId) return
    const isHour = field === 'hour'
    const isMinute = field === 'minute'
    const min = field === 'month' || field === 'day' ? 1 : 0
    const max = isHour ? 23 : isMinute ? 59 : field === 'month' ? 12 : 31
    const nextValue = clamp(Math.round(value), min, max)
    const nextTime = { ...(selectedDraft?.time ?? defaultTime()), [field]: nextValue }
    updateLabelDraft(selectedBoxId, { time: nextTime })
  }

  const syncCurrentTime = () => {
    if (!selectedBoxId) return
    updateLabelDraft(selectedBoxId, { time: defaultTime() })
  }

  // 自动补充描述：首次选中某个框且描述为空/模板时自动生成
  useEffect(() => {
    if (!selectedBoxId || !selectedDraft) return
    const desc = (selectedDraft.description || '').trim()
    const isPlaceholder =
      !desc || descriptionPool.includes(desc) || desc.startsWith('在这里写下物品的故事')
    if (isPlaceholder && !describedRef.current.has(selectedBoxId)) {
      void runDescriptionGeneration(selectedDraft.name || '这件物品', selectedDraft.category || '杂物', selectedBoxId)
    }
  }, [selectedBoxId, selectedDraft, runDescriptionGeneration])

  const handleTagPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!selectedBoxId || !previewRef.current || !tagRef.current || !selectedDraft) return
    event.preventDefault()
    const containerRect = previewRef.current.getBoundingClientRect()
    const tagRect = tagRef.current.getBoundingClientRect()
    const startX = event.clientX
    const startY = event.clientY
    const startPos = selectedDraft.tagPosition

    const halfWidthPercent = (tagRect.width / containerRect.width) / 2
    const halfHeightPercent = (tagRect.height / containerRect.height) / 2

    const handleMove = (moveEvent: PointerEvent) => {
      const deltaX = moveEvent.clientX - startX
      const deltaY = moveEvent.clientY - startY
      const absoluteX = startPos.xPercent * containerRect.width + deltaX
      const absoluteY = startPos.yPercent * containerRect.height + deltaY
      const nextXPercent = clamp(absoluteX / containerRect.width, halfWidthPercent, 1 - halfWidthPercent)
      const nextYPercent = clamp(absoluteY / containerRect.height, halfHeightPercent, 1 - halfHeightPercent)
      updateLabelDraft(selectedBoxId, {
        tagPosition: { xPercent: nextXPercent, yPercent: nextYPercent },
      })
    }

    const handleUp = () => {
      window.removeEventListener('pointermove', handleMove)
      window.removeEventListener('pointerup', handleUp)
      setTagDragging(false)
    }

    setTagDragging(true)
    window.addEventListener('pointermove', handleMove)
    window.addEventListener('pointerup', handleUp)
  }

  const handleScaleHandleDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!selectedBoxId || !previewRef.current || !tagRef.current || !selectedDraft) return
    event.preventDefault()
    event.stopPropagation()
    const containerRect = previewRef.current.getBoundingClientRect()
    const tagRect = tagRef.current.getBoundingClientRect()
    const baseWidth = tagRect.width / selectedDraft.tagScale
    const baseHeight = tagRect.height / selectedDraft.tagScale
    const startScale = selectedDraft.tagScale
    const startX = event.clientX
    const startY = event.clientY

    const handleMove = (moveEvent: PointerEvent) => {
      const delta = (moveEvent.clientX - startX + (moveEvent.clientY - startY)) / 220
      const nextScale = clamp(startScale + delta, 0.7, 1.6)
      const scaledWidth = baseWidth * nextScale
      const scaledHeight = baseHeight * nextScale
      const halfWidthPercent = scaledWidth / containerRect.width / 2
      const halfHeightPercent = scaledHeight / containerRect.height / 2

      const currentPos = useCaptureStore.getState().labelDrafts[selectedBoxId]?.tagPosition ?? {
        xPercent: 0.5,
        yPercent: 0.5,
      }

      const clampedX = clamp(currentPos.xPercent, halfWidthPercent, 1 - halfWidthPercent)
      const clampedY = clamp(currentPos.yPercent, halfHeightPercent, 1 - halfHeightPercent)

      updateLabelDraft(selectedBoxId, {
        tagScale: nextScale,
        tagPosition: { xPercent: clampedX, yPercent: clampedY },
      })
    }

    const handleUp = () => {
      window.removeEventListener('pointermove', handleMove)
      window.removeEventListener('pointerup', handleUp)
    }

    window.addEventListener('pointermove', handleMove)
    window.addEventListener('pointerup', handleUp)
  }

  const handleTimePointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!selectedBoxId || !previewRef.current || !timeRef.current || !selectedDraft) return
    event.preventDefault()
    const containerRect = previewRef.current.getBoundingClientRect()
    const timeRect = timeRef.current.getBoundingClientRect()
    const startX = event.clientX
    const startY = event.clientY
    const startPos = selectedDraft.timePosition ?? { xPercent: 0.83, yPercent: 0.14 }

    const halfWidthPercent = (timeRect.width / containerRect.width) / 2
    const halfHeightPercent = (timeRect.height / containerRect.height) / 2

    const handleMove = (moveEvent: PointerEvent) => {
      const deltaX = moveEvent.clientX - startX
      const deltaY = moveEvent.clientY - startY
      const absoluteX = startPos.xPercent * containerRect.width + deltaX
      const absoluteY = startPos.yPercent * containerRect.height + deltaY
      const nextXPercent = clamp(absoluteX / containerRect.width, halfWidthPercent, 1 - halfWidthPercent)
      const nextYPercent = clamp(absoluteY / containerRect.height, halfHeightPercent, 1 - halfHeightPercent)
      updateLabelDraft(selectedBoxId, {
        timePosition: { xPercent: nextXPercent, yPercent: nextYPercent },
      })
    }

    const handleUp = () => {
      window.removeEventListener('pointermove', handleMove)
      window.removeEventListener('pointerup', handleUp)
      setTimeDragging(false)
    }

    setTimeDragging(true)
    window.addEventListener('pointermove', handleMove)
    window.addEventListener('pointerup', handleUp)
  }

  const handleTimeScaleHandleDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!selectedBoxId || !previewRef.current || !timeRef.current || !selectedDraft) return
    event.preventDefault()
    event.stopPropagation()
    const containerRect = previewRef.current.getBoundingClientRect()
    const timeRect = timeRef.current.getBoundingClientRect()
    const startScale = selectedDraft.timeScale ?? 1
    const baseWidth = timeRect.width / startScale
    const baseHeight = timeRect.height / startScale
    const startX = event.clientX
    const startY = event.clientY

    const handleMove = (moveEvent: PointerEvent) => {
      const delta = (moveEvent.clientX - startX + (moveEvent.clientY - startY)) / 220
      const nextScale = clamp(startScale + delta, 0.7, 1.6)
      const scaledWidth = baseWidth * nextScale
      const scaledHeight = baseHeight * nextScale
      const halfWidthPercent = scaledWidth / containerRect.width / 2
      const halfHeightPercent = scaledHeight / containerRect.height / 2

      const currentPos = useCaptureStore.getState().labelDrafts[selectedBoxId]?.timePosition ?? {
        xPercent: 0.83,
        yPercent: 0.14,
      }

      const clampedX = clamp(currentPos.xPercent, halfWidthPercent, 1 - halfWidthPercent)
      const clampedY = clamp(currentPos.yPercent, halfHeightPercent, 1 - halfHeightPercent)

      updateLabelDraft(selectedBoxId, {
        timeScale: nextScale,
        timePosition: { xPercent: clampedX, yPercent: clampedY },
      })
    }

    const handleUp = () => {
      window.removeEventListener('pointermove', handleMove)
      window.removeEventListener('pointerup', handleUp)
    }

    window.addEventListener('pointermove', handleMove)
    window.addEventListener('pointerup', handleUp)
  }

  const capturePreview = useCallback(async () => {
    if (!previewRef.current) return null
    const canvas = await html2canvas(previewRef.current, {
      backgroundColor: null,
      scale: 1,
      useCORS: true,
      allowTaint: true,
      ignoreElements: (element) =>
        element instanceof HTMLElement && element.dataset.captureIgnore === 'true',
    })
    return canvas.toDataURL('image/png')
  }, [])

  const handleSave = async () => {
    if (!pixelPreviewUrl || detectionBoxes.length === 0 || !selectedBoxId || !selectedDraft) return
    const selectedBox = detectionBoxes.find((box) => box.id === selectedBoxId)
    setSaveStatus('saving')
    setSaveMessage(null)
    let composedImage: string | null = null
    try {
      composedImage = await capturePreview()
    } catch (error) {
      console.error('捕捉预览失败，使用后端合成', error)
    }
    const payload: SaveArtworkPayload = {
      user_id: 'guest',
      base_image: pixelPreviewUrl,
      composed_image: composedImage ?? undefined,
      label: {
        name: selectedDraft.name || '未命名物品',
        category: selectedDraft.category || '杂物',
        description: selectedDraft.description || '在这里写下物品的故事。',
        energy: selectedDraft.energy,
        health: selectedDraft.health,
        time: selectedDraft.time ?? defaultTime(),
        tag_position: {
          x_percent: selectedDraft.tagPosition?.xPercent ?? 0.5,
          y_percent: selectedDraft.tagPosition?.yPercent ?? 0.5,
        },
        tag_scale: selectedDraft.tagScale ?? 1,
      },
      box_bounds: selectedBox?.bounds,
    }

    try {
      await saveArtwork(payload)
      setSaveStatus('success')
      setSaveMessage('已放入珍藏！')
    } catch (error) {
      setSaveStatus('error')
      setSaveMessage('没能放进珍藏…再试一次？')
      console.error('保存失败', error)
    }
  }

  const canSave = detectionBoxes.length > 0 && !!pixelPreviewUrl && !isGeneratingPixel && !detecting

  const timeState = selectedDraft?.time ?? defaultTime()
  const timePosition = selectedDraft?.timePosition ?? { xPercent: 0.83, yPercent: 0.14 }
  const timeScale = selectedDraft?.timeScale ?? 1
  const hourAngle = ((timeState.hour % 12) + timeState.minute / 60) * 30
  const minuteAngle = timeState.minute * 6

  return (
    <div className="page capture-page">
      <header className="page-header capture-header">
        <div>
          <p className="eyebrow">捕物界面</p>
          <h1>像素预览与三联动</h1>
          <p className="lede">
            上传后自动压缩到 720–1600px，后端生图 + 阿里云识别默认选中最大物体，物品栏/框/表单实时联动，便签可拖拽缩放且不越界。
          </p>
        </div>
        <Link className="ghost-button return-button" to="/">
          返回主页
        </Link>
      </header>

      <div className="capture-layout">
        <div className="workspace">
          <section className="pane preview-pane">
            <div className="pane-top">
              <div className="pane-title">左侧预览区</div>
              <span className="helper-text subtle">
                {uploadFile ? `已压缩：${uploadFile.name}` : '状态：未上传'}
              </span>
            </div>

            <div className="preview-stage wood-frame">
              <div className="preview-paper paper-sheet">
                <div
                  className={`preview-canvas ${isDragging ? 'dragging' : ''}`}
                  onDragOver={handleDragOver}
                  onDragEnter={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  ref={previewRef}
                >
                  {!displayedPreview && (
                    <div
                      className="empty-canvas interactive"
                      onKeyDown={handleEmptyKeyDown}
                      role="button"
                      tabIndex={0}
                    >
                      <label className="pixel-button primary" htmlFor={fileInputId}>
                        上传图片
                      </label>
                    </div>
                  )}

                  {displayedPreview && (
                    <img alt="上传预览" className="preview-image" src={displayedPreview} />
                  )}

                  <div className="box-layer">
                    {displayedBoxes.map((box) => {
                      const draftName = labelDrafts[box.id]?.name?.trim()
                      const displayName = draftName || box.label || '物体'
                      return (
                        <button
                          key={box.id}
                          type="button"
                          className={`box-outline ${box.id === selectedBoxId ? 'active' : ''}`}
                          style={{
                            top: `${box.bounds.y * 100}%`,
                            left: `${box.bounds.x * 100}%`,
                            width: `${box.bounds.width * 100}%`,
                            height: `${box.bounds.height * 100}%`,
                          }}
                          onClick={() => selectBox(box.id)}
                        >
                          <span className="box-label">{displayName}</span>
                        </button>
                      )
                    })}
                  </div>

                  {selectedDraft && (
                    <div className="tag-layer">
                      <div
                        ref={tagRef}
                        className={`tag-card ${tagDragging ? 'dragging' : ''}`}
                        style={{
                          left: `${(selectedDraft.tagPosition?.xPercent ?? 0.5) * 100}%`,
                          top: `${(selectedDraft.tagPosition?.yPercent ?? 0.5) * 100}%`,
                          transform: `translate(-50%, -50%) scale(${selectedDraft.tagScale})`,
                        }}
                        onPointerDown={handleTagPointerDown}
                      >
                        <div className="tag-name-row">{selectedDraft.name || '未命名物品'}</div>
                        <div className="tag-divider" />
                        <div className="tag-category-text">{selectedDraft.category || '类别'}</div>
                        <div className="tag-divider thick" />
                        <div className="tag-body">
                          <p>{selectedDraft.description || '在这里写下物品的故事，或点击右侧重生按钮。'}</p>
                        </div>
                        {(selectedDraft.category === '菜品' || selectedDraft.category === '食物') && (
                          <div className="tag-stats">
                            <div className="tag-stat">
                              <span className="stat-icon energy" />
                              <span className="stat-label">+{selectedDraft.energy} 能量</span>
                            </div>
                            <div className="tag-stat">
                              <span className="stat-icon health" />
                              <span className="stat-label">+{selectedDraft.health} 生命值</span>
                            </div>
                          </div>
                        )}
                        <div className="tag-handle" onPointerDown={handleScaleHandleDown}>
                          ⤢
                        </div>
                      </div>
                    </div>
                  )}

                  {displayedPreview && (
                    <div
                      ref={timeRef}
                      className={`time-coin-placeholder ${timeDragging ? 'dragging' : ''}`}
                      style={{
                        left: `${timePosition.xPercent * 100}%`,
                        top: `${timePosition.yPercent * 100}%`,
                        transform: `translate(-50%, -50%) scale(${timeScale})`,
                      }}
                      onPointerDown={handleTimePointerDown}
                    >
                      <div className="time-widget">
                        <div className="time-meta">
                          <span className="time-day">
                            {timeState.month ?? 1}月{timeState.day ?? 1}日
                          </span>
                          <span className="time-text">{formatTime(timeState.hour, timeState.minute)}</span>
                        </div>
                        <div className="clock-face">
                          <div className="clock-hand hour" style={{ transform: `rotate(${hourAngle}deg)` }} />
                          <div className="clock-hand minute" style={{ transform: `rotate(${minuteAngle}deg)` }} />
                          <div className="clock-center" />
                        </div>
                      </div>
                      <div className="coin-chip">88888888</div>
                      <div className="time-handle" onPointerDown={handleTimeScaleHandleDown}>
                        ⤢
                      </div>
                    </div>
                  )}

                  {isGeneratingPixel && (
                    <div className="preview-status floating" data-capture-ignore="true">
                      <span className="status-dot" />
                      正在生成像素预览...
                    </div>
                  )}

                  {detecting && (
                    <div className="preview-status subtle" data-capture-ignore="true">
                      正在识别物体...
                    </div>
                  )}
                  {generationNote && (
                    <div className="preview-status subtle" data-capture-ignore="true">
                      {generationNote}
                    </div>
                  )}
                  {uploadError && (
                    <div className="upload-error" data-capture-ignore="true">
                      {uploadError}
                    </div>
                  )}
                  {uploadFile && (
                    <div className="upload-file-info" data-capture-ignore="true">
                      <span className="file-name">
                        {uploadFile.name}
                        {resizeInfo ? ` · ${resizeInfo.width}×${resizeInfo.height}` : ''}
                      </span>
                      <button className="text-button" type="button" onClick={handleBrowseClick}>
                        换图
                      </button>
                    </div>
                  )}
                  <input
                    id={fileInputId}
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    className={displayedPreview ? 'sr-only' : 'file-overlay'}
                    onChange={handleFileChange}
                  />
                </div>
              </div>
            </div>
          </section>

          <section className="pane editor-pane">
            <div className="pane-top">
              <div className="pane-title">右侧编辑面板</div>
              <span className="helper-text subtle">
                {selectedDraft ? '改动后左侧立即同步' : '选中一个识别框后开始编辑'}
              </span>
            </div>
            <div className="editor-stacks">
              <div className="panel-card form-placeholder rpg-panel">
                <div className="paper-sheet">
                  {selectedDraft ? (
                    <div className="form-grid">
                      <div className="form-row paper-field">
                        <span>名称</span>
                        <div className="field-with-action">
                          <input
                            className="input-wood"
                            value={selectedDraft.name}
                            onChange={(event) => updateLabelDraft(selectedBoxId!, { name: event.target.value })}
                            placeholder="给物品起个星露谷名字"
                          />
                          <button
                            className="mini-chip"
                            type="button"
                            onClick={handleNameSuggestion}
                            disabled={nameLoading || !previewUrl}
                          >
                            {nameLoading ? '取名中…' : '取名'}
                          </button>
                        </div>
                      </div>
                      <div className="form-row paper-field">
                        <span>类别</span>
                        <select
                          className="input-wood"
                          value={selectedDraft.category}
                          onChange={(event) => handleCategoryChange(event.target.value)}
                        >
                          {categoryOptions.map((option) => (
                            <option key={option} value={option}>
                              {option}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="form-row paper-field">
                        <span>描述</span>
                        <div className="field-with-action">
                          <textarea
                            className="input-wood tall"
                            value={selectedDraft.description}
                            onChange={(event) => updateLabelDraft(selectedBoxId!, { description: event.target.value })}
                            placeholder="写 1–2 句星露谷口吻的描述"
                          />
                          <button
                            className="mini-chip"
                            type="button"
                            onClick={handleDescriptionGenerate}
                            disabled={descriptionLoading}
                          >
                            {descriptionLoading ? '生成中...' : '重生'}
                          </button>
                        </div>
                      </div>
                      {(selectedDraft.category === '菜品' || selectedDraft.category === '食物') && (
                        <div className="form-row split paper-field">
                          <div className="stat-ghost">
                            <span>能量</span>
                            <div className="stat-field">
                              <button
                                className="mini-chip ghost"
                                type="button"
                                onClick={() => adjustStat('energy', -5)}
                              >
                                -
                              </button>
                              <input
                                className="input-wood"
                                type="number"
                                value={selectedDraft.energy}
                                min={0}
                                max={200}
                                onChange={(event) => handleStatChange('energy', Number(event.target.value))}
                              />
                              <button
                                className="mini-chip ghost"
                                type="button"
                                onClick={() => adjustStat('energy', 5)}
                              >
                                +
                              </button>
                            </div>
                          </div>
                          <div className="stat-ghost">
                            <span>生命值</span>
                            <div className="stat-field">
                              <button
                                className="mini-chip ghost"
                                type="button"
                                onClick={() => adjustStat('health', -5)}
                              >
                                -
                              </button>
                              <input
                                className="input-wood"
                                type="number"
                                value={selectedDraft.health}
                                min={0}
                                max={200}
                                onChange={(event) => handleStatChange('health', Number(event.target.value))}
                              />
                              <button
                                className="mini-chip ghost"
                                type="button"
                                onClick={() => adjustStat('health', 5)}
                              >
                                +
                              </button>
                            </div>
                          </div>
                        </div>
                      )}
                      <div className="form-row paper-field">
                        <span>时间</span>
                        <div className="field-with-action">
                          <div className="time-inputs">
                            <div className="time-row">
                              <label className="time-chip">
                                <span>月</span>
                                <input
                                  className="input-wood"
                                  type="number"
                                  min={1}
                                  max={12}
                                  value={timeState.month}
                                  onChange={(event) => handleTimeChange('month', Number(event.target.value))}
                                />
                              </label>
                              <label className="time-chip">
                                <span>日</span>
                                <input
                                  className="input-wood"
                                  type="number"
                                  min={1}
                                  max={31}
                                  value={timeState.day}
                                  onChange={(event) => handleTimeChange('day', Number(event.target.value))}
                                />
                              </label>
                            </div>
                            <div className="time-row">
                              <label className="time-chip">
                                <span>时</span>
                                <input
                                  className="input-wood"
                                  type="number"
                                  min={0}
                                  max={23}
                                  value={timeState.hour}
                                  onChange={(event) => handleTimeChange('hour', Number(event.target.value))}
                                />
                              </label>
                              <label className="time-chip">
                                <span>分</span>
                                <input
                                  className="input-wood"
                                  type="number"
                                  min={0}
                                  max={59}
                                  value={timeState.minute}
                                  onChange={(event) => handleTimeChange('minute', Number(event.target.value))}
                                />
                              </label>
                            </div>
                          </div>
                          <button className="mini-chip" type="button" onClick={syncCurrentTime}>
                            同步当前时间
                          </button>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="form-grid placeholder-grid">
                      <p className="helper-text">等待上传照片并选择识别框后，可在此编辑标签内容。</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </section>

          <section className="object-bar">
            <div className="object-bar-header">
              <span>物品栏</span>
              <span className="helper-text">
                {detectionBoxes.length > 0
                  ? `识别到 ${detectionBoxes.length} 个物体 · 第 ${currentPage + 1}/${totalPages} 页`
                  : '等待识别结果'}
              </span>
              {detectionBoxes.length > PAGE_SIZE && (
                <div className="pager">
                  <button
                    className="mini-chip ghost"
                    type="button"
                    onClick={() => setObjectPage((page) => Math.max(0, page - 1))}
                    disabled={currentPage === 0}
                  >
                    上一页
                  </button>
                  <button
                    className="mini-chip ghost"
                    type="button"
                    onClick={() => setObjectPage((page) => Math.min(totalPages - 1, page + 1))}
                    disabled={currentPage >= totalPages - 1}
                  >
                    下一页
                  </button>
                </div>
              )}
            </div>
            <div className="object-grid">
              {pagedBoxes.map((box, index) => {
                const displayIndex = index + 1 + currentPage * PAGE_SIZE
                const displayName = labelDrafts[box.id]?.name || box.label || '未命名'
                return (
                  <button
                    key={box.id}
                    type="button"
                    className={`object-slot ${box.id === selectedBoxId ? 'active' : ''}`}
                    onClick={() => selectBox(box.id)}
                  >
                    <div className="slot-label">#{displayIndex} {displayName}</div>
                    <div className="slot-hint">{box.id === selectedBoxId ? '当前已选中' : '点击切换'}</div>
                  </button>
                )
              })}
            </div>
          </section>
        </div>

        <div className="bottom-actions solo">
          <button
            className="pixel-button primary"
            type="button"
            onClick={handleSave}
            disabled={!canSave}
          >
            {saveStatus === 'saving' ? '保存中...' : saveStatus === 'success' ? '已保存' : '保存至珍藏箱'}
          </button>
          {saveMessage && <div className={`save-hint ${saveStatus === 'error' ? 'error' : 'success'}`}>{saveMessage}</div>}
        </div>
      </div>
    </div>
  )
}

export default CapturePage
