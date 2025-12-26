import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { listArtworks, type ArtworkRecord } from '../api/client'

const PAGE_SIZE = 12

const formatTime = (value: string) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

const CollectionPage = () => {
  const [artworks, setArtworks] = useState<ArtworkRecord[]>([])
  const [page, setPage] = useState(0)
  const [total, setTotal] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeArtwork, setActiveArtwork] = useState<ArtworkRecord | null>(null)

  const totalPages = useMemo(() => {
    if (total != null) {
      return Math.max(1, Math.ceil(total / PAGE_SIZE))
    }
    return artworks.length === PAGE_SIZE ? page + 2 : Math.max(1, page + 1)
  }, [artworks.length, page, total])

  const canNext = useMemo(() => {
    if (total != null) {
      return page < totalPages - 1
    }
    return artworks.length === PAGE_SIZE
  }, [artworks.length, page, totalPages, total])

  const fetchPage = useCallback(
    async (pageIndex: number) => {
      setLoading(true)
      setError(null)
      try {
        const response = await listArtworks(PAGE_SIZE, pageIndex * PAGE_SIZE)
        setArtworks(response.items)
        setTotal(response.total ?? null)
      } catch (err) {
        setError('珍藏加载失败，刷新或稍后再试')
        console.error('加载珍藏失败', err)
      } finally {
        setLoading(false)
      }
    },
    [],
  )

  useEffect(() => {
    void fetchPage(page)
  }, [fetchPage, page])

  return (
    <div className="page collection-page">
      <div className="collection-room">
        <header className="collection-header">
          <div className="collection-plaque">
            <span className="plaque-title">珍藏室</span>
            <span className="plaque-sub">2D 像素 RPG 图鉴风</span>
          </div>
          <div className="collection-actions">
            <div className="pager">
              <button
                className="mini-chip ghost"
                type="button"
                onClick={() => setPage((value) => Math.max(0, value - 1))}
                disabled={page === 0 || loading}
              >
                上一页
              </button>
              <span className="helper-text subtle">
                第 {page + 1}/{totalPages} 页
              </span>
              <button
                className="mini-chip ghost"
                type="button"
                onClick={() => canNext && setPage((value) => value + 1)}
                disabled={!canNext || loading}
              >
                下一页
              </button>
            </div>
            <Link className="ghost-button" to="/">
              返回主页
            </Link>
          </div>
        </header>

        {error && <div className="upload-error">{error}</div>}
        {loading && <div className="preview-status subtle">正在加载珍藏...</div>}

        <section className="collection-grid">
          {artworks.length === 0 && !loading ? (
            <div className="helper-text subtle">还没有作品，去捕物页试试吧。</div>
          ) : (
            artworks.map((artwork, index) => (
              <button key={artwork.id} className="collection-card" tabIndex={0} onClick={() => setActiveArtwork(artwork)}>
                <div className="card-number">{index + 1 + page * PAGE_SIZE}</div>
                <div className="card-frame">
                  <div className="card-paper">
                    <div
                      className="card-thumb"
                      style={{ backgroundImage: `url(${artwork.url})`, backgroundSize: 'cover', backgroundPosition: 'center' }}
                    >
                      {!artwork.url && `作品 ${artwork.id}`}
                    </div>
                    <div className="card-meta">
                      <span className="card-title">作品 {artwork.id.slice(0, 6)}</span>
                      <span className="card-info">保存时间：{formatTime(artwork.created_at)}</span>
                    </div>
                  </div>
                </div>
              </button>
            ))
          )}
        </section>

        {activeArtwork && (
          <div className="modal-overlay" role="dialog" aria-label="查看作品">
            <div className="modal-card">
              <div className="modal-header">
                <span>作品 {activeArtwork.id}</span>
                <button className="ghost-button" type="button" onClick={() => setActiveArtwork(null)}>
                  关闭
                </button>
              </div>
              <div className="modal-body">
                <img src={activeArtwork.url} alt={`作品 ${activeArtwork.id}`} className="modal-image" />
                <div className="modal-meta">保存时间：{formatTime(activeArtwork.created_at)}</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default CollectionPage
