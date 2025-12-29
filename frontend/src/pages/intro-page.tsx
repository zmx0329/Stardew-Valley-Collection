import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAudioStore } from '../state/audio-store'
import { ensureAudioContext, playTypeBeep } from '../utils/sfx'

const letterParagraphs = [
  '亲爱的孩子：',
  '就在今天，我在报纸上看到了关于你的报道！你竟然已经变得这么优秀了。我不禁感叹，时间过得真是太快了……仿佛就在昨天，你还只是那个在大树下追逐蝴蝶的小身影。',
  '看着你在那个繁华的世界里获得成功，我打心底里为你骄傲。但我也从字里行间读出了一丝疲惫。那个钢筋混铁的城市，一切似乎都变得冰冷而仓促。',
  '别让忙碌偷走了你的眼睛。为了庆祝你的成就，我为你准备了一个特别的礼物。它能带你穿透平庸的日常，看清生活本来的面目。',
  '当你觉得世界太快、太模糊时，打开它，你会发现平凡的一日三餐、窗边的旧书，其实都闪烁着星露谷的光芒。',
  '别担心，慢慢来。生活本身就是一场最伟大的冒险。',
]

const cinematicScenes = [
  '嘘……听到了吗？那是森林里的微风吹过窗棂的声音。',
  '你是否也察觉到了？周围的世界，似乎正在悄悄褪去灰色的外壳。',
  '桌上那杯冒热气的咖啡？那是刚采摘的咖啡豆，带着清晨的露水。\n阳台上落下的几片叶子？那是祝尼魔留下的恶作剧足迹。\n甚至连你那只总是发呆的猫……它似乎也正准备在午后的暖阳里，为你带回一份神秘的礼物。',
  '不必惊讶，这才是世界最纯粹的模样。\n我已赋予你【真视之眼】。用它去洞察这个世界吧。去寻找那些被你遗忘的、闪着光的瞬间。',
  '将现实的物品收入囊中，重塑成星露谷的记忆。\n在这里，建立属于你的生活物语。',
]

type IntroPhase = 'letter' | 'transition' | 'cinematic'

const IntroPage = () => {
  const navigate = useNavigate()
  const pauseForCinematic = useAudioStore((state) => state.pauseForCinematic)
  const [phase, setPhase] = useState<IntroPhase>('letter')
  const [sceneIndex, setSceneIndex] = useState(0)
  const [typedText, setTypedText] = useState('')
  const charIndexRef = useRef(0)
  const timeoutsRef = useRef<number[]>([])
  const clearTimers = useCallback(() => {
    timeoutsRef.current.forEach((timeoutId) => window.clearTimeout(timeoutId))
    timeoutsRef.current = []
  }, [])

  const schedule = useCallback((callback: () => void, delay: number) => {
    const timeoutId = window.setTimeout(callback, delay)
    timeoutsRef.current.push(timeoutId)
  }, [])

  const handleGiftClick = useCallback(async () => {
    if (phase !== 'letter') {
      return
    }
    clearTimers()
    await ensureAudioContext()
    pauseForCinematic()
    setTypedText('')
    setSceneIndex(0)
    setPhase('transition')
    schedule(() => setPhase('cinematic'), 650)
  }, [clearTimers, ensureAudioContext, pauseForCinematic, phase, schedule])

  const handleSkip = useCallback(() => {
    clearTimers()
    navigate('/home')
  }, [clearTimers, navigate])

  useEffect(() => {
    if (phase !== 'cinematic') {
      return () => {}
    }

    clearTimers()
    const sceneText = cinematicScenes[sceneIndex] ?? ''
    charIndexRef.current = 0
    setTypedText('')

    const getDelayForChar = (char: string) => {
      if (char === '\n') {
        return 360
      }
      if (/[，。！？…；：]/.test(char)) {
        return 220
      }
      if (/\s/.test(char)) {
        return 70
      }
      return 80
    }

    const typeNext = () => {
      const nextIndex = charIndexRef.current + 1
      const nextChar = sceneText[nextIndex - 1] ?? ''
      charIndexRef.current = nextIndex
      setTypedText(sceneText.slice(0, nextIndex))
      if (nextChar && !/\s/.test(nextChar)) {
        playTypeBeep()
      }
      if (nextIndex >= sceneText.length) {
        schedule(() => {
          if (sceneIndex < cinematicScenes.length - 1) {
            setSceneIndex((prev) => prev + 1)
          } else {
            navigate('/home')
          }
        }, 1800)
        return
      }
      schedule(typeNext, getDelayForChar(nextChar))
    }

    schedule(typeNext, 80)

    return () => clearTimers()
  }, [clearTimers, navigate, phase, playTypeBeep, sceneIndex, schedule])

  useEffect(() => () => clearTimers(), [clearTimers])

  const isFading = phase !== 'letter'
  const isBlackout = phase !== 'letter'
  const sceneText = cinematicScenes[sceneIndex] ?? ''

  return (
    <div className="intro-page">
      <div className="intro-letter-stage">
        <div className={`intro-letter ${isFading ? 'is-fading' : ''}`}>
          <div className="intro-letter-content">
            {letterParagraphs.map((paragraph) => (
              <p key={paragraph}>{paragraph}</p>
            ))}
            <p className="intro-letter-signoff">爱你的，祖父</p>
          </div>
          <div className="intro-gift-anchor">
            <button className="intro-gift-button" type="button" onClick={handleGiftClick} aria-label="打开礼物">
              <span className="intro-gift-icon" aria-hidden="true" />
            </button>
          </div>
        </div>
      </div>
      <div className={`intro-cinematic ${isBlackout ? 'is-active' : ''}`}>
        <div className="intro-cinematic-text">
          <span className="intro-cinematic-placeholder" aria-hidden="true">
            {sceneText}
          </span>
          <span className="intro-cinematic-typed">{typedText}</span>
        </div>
        {isBlackout && (
          <button className="intro-skip" type="button" onClick={handleSkip}>
            跳过
          </button>
        )}
      </div>
    </div>
  )
}

export default IntroPage
