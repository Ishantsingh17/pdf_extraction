import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'

import type { DocumentInfo, SourceRef } from '../types'
import { ChevronLeft, ChevronRight, LinkIcon, MinusIcon, PlusIcon } from './icons'

// Recommended worker setup for bundlers (react-pdf docs).
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

interface DocumentViewerProps {
  document: DocumentInfo
  /** Source region of the field the user selected, if any. */
  activeSource: SourceRef | null
  /** Label shown in the "navigated to source" toast. */
  activeLabel?: string | null
}

const ZOOM_STEPS = [50, 75, 100, 125, 150, 200, 300]
const VIEWER_PADDING = 32

/**
 * Renders the *actual uploaded document*. Nothing here is generated: PDFs are
 * drawn by pdf.js from the original bytes, images are shown as uploaded. The
 * only things layered on top are the source highlight and the page chrome.
 */
export function DocumentViewer({ document: doc, activeSource, activeLabel }: DocumentViewerProps) {
  const previewUrl = doc.preview_url
  const isPdf = doc.file_type === 'pdf'

  const [pageNumber, setPageNumber] = useState(1)
  const [pageCount, setPageCount] = useState(doc.page_count || 1)
  const [zoom, setZoom] = useState(100)
  const [fitWidth, setFitWidth] = useState(false)
  const [pageSize, setPageSize] = useState<{ width: number; height: number } | null>(null)
  const [viewportWidth, setViewportWidth] = useState(0)
  const [loadError, setLoadError] = useState<string | null>(null)

  const stageRef = useRef<HTMLDivElement>(null)
  const highlightRef = useRef<HTMLDivElement>(null)
  const autoFitted = useRef(false)

  // A phone photo or a 200-dpi scan is far wider than the viewer. Show the
  // whole page first - the user can still zoom to 100% from the toolbar.
  useEffect(() => {
    if (autoFitted.current || !pageSize || !viewportWidth) return
    autoFitted.current = true
    if (pageSize.width > viewportWidth - VIEWER_PADDING * 2) setFitWidth(true)
  }, [pageSize, viewportWidth])

  // Keep the viewport width current so "Fit Width" stays honest on resize.
  useEffect(() => {
    const element = stageRef.current
    if (!element) return
    const observer = new ResizeObserver((entries) => {
      setViewportWidth(entries[0].contentRect.width)
    })
    observer.observe(element)
    setViewportWidth(element.clientWidth)
    return () => observer.disconnect()
  }, [])

  // Selecting a field moves the viewer to that field's page.
  useEffect(() => {
    if (activeSource?.page && activeSource.page !== pageNumber) {
      setPageNumber(activeSource.page)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSource])

  useEffect(() => {
    if (!activeSource) return
    const timer = window.setTimeout(() => {
      highlightRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' })
    }, 80)
    return () => window.clearTimeout(timer)
  }, [activeSource, pageNumber, zoom, fitWidth])

  const scale = useMemo(() => {
    if (fitWidth && pageSize && viewportWidth) {
      return (viewportWidth - VIEWER_PADDING * 2) / pageSize.width
    }
    return zoom / 100
  }, [fitWidth, pageSize, viewportWidth, zoom])

  const zoomLabel = fitWidth && pageSize ? `${Math.round(scale * 100)}%` : `${zoom}%`

  const stepZoom = useCallback(
    (direction: -1 | 1) => {
      setFitWidth(false)
      setZoom((current) => {
        const effective = fitWidth && pageSize ? Math.round(scale * 100) : current
        if (direction === 1) return ZOOM_STEPS.find((step) => step > effective) ?? effective
        return [...ZOOM_STEPS].reverse().find((step) => step < effective) ?? effective
      })
    },
    [fitWidth, pageSize, scale],
  )

  const onPdfLoad = useCallback(({ numPages }: { numPages: number }) => {
    setPageCount(numPages)
    setLoadError(null)
  }, [])

  const onPageLoad = useCallback((page: { originalWidth: number; originalHeight: number }) => {
    setPageSize({ width: page.originalWidth, height: page.originalHeight })
  }, [])

  const onImageLoad = useCallback((event: React.SyntheticEvent<HTMLImageElement>) => {
    const image = event.currentTarget
    setPageSize({ width: image.naturalWidth, height: image.naturalHeight })
  }, [])

  const highlight = useMemo(() => {
    if (!activeSource || !pageSize || activeSource.page !== pageNumber) return null
    const [x0, y0, x1, y1] = activeSource.bbox as number[]
    if ([x0, y0, x1, y1].some((value) => typeof value !== 'number')) return null
    // Source coordinates are in the page's own space; scale them to the
    // rendering the user is currently looking at.
    return {
      left: x0 * scale,
      top: y0 * scale,
      width: Math.max((x1 - x0) * scale, 8),
      height: Math.max((y1 - y0) * scale, 8),
    }
  }, [activeSource, pageSize, pageNumber, scale])

  const showRail = pageCount > 1

  return (
    <section className="card flex min-h-0 flex-1 flex-col overflow-hidden">
      {/* Toolbar */}
      <div className="flex h-[51px] shrink-0 items-center gap-2.5 border-b border-line px-5">
        <h2 className="text-base font-semibold text-ink">Bill Preview</h2>
        <span className="max-w-[220px] truncate rounded-md bg-page px-2 py-1 text-xs text-ink-subtle">
          {doc.filename}
        </span>

        <div className="ml-auto flex items-center gap-2">
          <div className="flex items-center gap-1">
            <ToolbarButton label="Zoom out" onClick={() => stepZoom(-1)}>
              <MinusIcon size={14} />
            </ToolbarButton>
            <span className="w-12 text-center text-base font-medium tabular-nums text-ink">
              {zoomLabel}
            </span>
            <ToolbarButton label="Zoom in" onClick={() => stepZoom(1)}>
              <PlusIcon size={14} />
            </ToolbarButton>
          </div>
          <button
            type="button"
            onClick={() => setFitWidth((value) => !value)}
            aria-pressed={fitWidth}
            className={`focus-ring h-9 rounded-control border px-3.5 text-base transition-colors ${
              fitWidth
                ? 'border-navy bg-navy-soft font-medium text-navy'
                : 'border-line bg-white text-ink hover:bg-page'
            }`}
          >
            Fit Width
          </button>
        </div>
      </div>

      <div className="flex min-h-0 flex-1">
        {/* Page thumbnails */}
        {showRail && (
          <aside className="w-rail shrink-0 space-y-2.5 overflow-y-auto border-r border-line bg-page p-3">
            {Array.from({ length: pageCount }, (_, index) => index + 1).map((number) => (
              <button
                key={number}
                type="button"
                onClick={() => setPageNumber(number)}
                aria-current={number === pageNumber}
                className={`focus-ring block w-full rounded-md border p-1 transition-colors ${
                  number === pageNumber
                    ? 'border-navy bg-navy-soft'
                    : 'border-line bg-white hover:border-navy-border'
                }`}
              >
                <span className="block overflow-hidden rounded-sm bg-white">
                  {isPdf ? (
                    <Document file={previewUrl} loading={<ThumbSkeleton />} error={<ThumbSkeleton />}>
                      <Page
                        pageNumber={number}
                        width={44}
                        renderTextLayer={false}
                        renderAnnotationLayer={false}
                        loading={<ThumbSkeleton />}
                      />
                    </Document>
                  ) : (
                    <img src={previewUrl} alt="" className="block w-full" />
                  )}
                </span>
                <span
                  className={`mt-1 block text-center text-2xs ${
                    number === pageNumber ? 'font-semibold text-navy' : 'text-ink-subtle'
                  }`}
                >
                  {number}
                </span>
              </button>
            ))}
          </aside>
        )}

        <div className="flex min-w-0 flex-1 flex-col">
          {/* The document itself - scrolls internally, never the page */}
          <div ref={stageRef} className="relative min-h-0 flex-1 overflow-auto bg-viewer-bg">
            <div className="flex min-h-full w-full justify-center p-8">
              <div className="relative h-fit shadow-viewerpage">
                <span className="absolute left-3 top-3 z-20 rounded-md border border-line bg-white/95 px-2 py-1 text-2xs font-medium text-ink-muted">
                  Page {pageNumber}
                </span>

                {isPdf ? (
                  <Document
                    file={previewUrl}
                    onLoadSuccess={onPdfLoad}
                    onLoadError={(error) => setLoadError(error.message)}
                    loading={<ViewerMessage>Loading your bill…</ViewerMessage>}
                    error={<ViewerMessage>This document could not be displayed.</ViewerMessage>}
                  >
                    <Page
                      pageNumber={pageNumber}
                      scale={scale}
                      onLoadSuccess={onPageLoad}
                      renderTextLayer={false}
                      renderAnnotationLayer={false}
                      loading={<ViewerMessage>Rendering page…</ViewerMessage>}
                    />
                  </Document>
                ) : (
                  <img
                    src={previewUrl}
                    alt={`Uploaded bill: ${doc.filename}`}
                    onLoad={onImageLoad}
                    style={pageSize ? { width: pageSize.width * scale } : undefined}
                    className="block max-w-none bg-white"
                  />
                )}

                {/* Source highlight, drawn over the untouched document */}
                {highlight && (
                  <div
                    ref={highlightRef}
                    className="pointer-events-none absolute z-10 rounded-[3px] border-2 border-highlight-border bg-highlight/55"
                    style={highlight}
                  >
                    <span className="absolute -right-px -top-7 rounded-md bg-ink px-2 py-1 text-2xs font-medium text-white">
                      source
                    </span>
                  </div>
                )}
              </div>
            </div>

            {activeSource && (
              <div className="pointer-events-none sticky bottom-4 left-0 flex justify-center px-8">
                <span className="inline-flex items-center gap-1.5 rounded-md border border-navy-border bg-white/95 px-2.5 py-1.5 text-xs font-medium text-navy shadow-card">
                  <LinkIcon size={13} />
                  Navigated to source · Page {activeSource.page}
                  {activeSource.anchor ? ` near “${activeSource.anchor}”` : ''}
                  {activeLabel ? ` · ${activeLabel}` : ''}
                </span>
              </div>
            )}

            {loadError && (
              <p className="absolute inset-x-0 bottom-6 text-center text-xs text-white/70">
                {loadError}
              </p>
            )}
          </div>

          {/* Page navigation */}
          <div className="flex h-12 shrink-0 items-center justify-center gap-3 bg-viewer-footer px-4">
            <button
              type="button"
              aria-label="Previous page"
              disabled={pageNumber <= 1}
              onClick={() => setPageNumber((value) => Math.max(1, value - 1))}
              className="focus-ring flex h-7 w-7 items-center justify-center rounded-md bg-white/10 text-white transition-colors hover:bg-white/20 disabled:opacity-40"
            >
              <ChevronLeft size={14} />
            </button>
            <span className="text-xs font-medium tabular-nums text-white">
              {pageNumber} / {pageCount}
            </span>
            <button
              type="button"
              aria-label="Next page"
              disabled={pageNumber >= pageCount}
              onClick={() => setPageNumber((value) => Math.min(pageCount, value + 1))}
              className="focus-ring flex h-7 w-7 items-center justify-center rounded-md bg-white/10 text-white transition-colors hover:bg-white/20 disabled:opacity-40"
            >
              <ChevronRight size={14} />
            </button>
            <span className="ml-3 text-xs text-white/55">Scroll inside viewer only</span>
          </div>
        </div>
      </div>
    </section>
  )
}

function ToolbarButton({
  children,
  label,
  onClick,
}: {
  children: React.ReactNode
  label: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      className="focus-ring flex h-9 w-9 items-center justify-center rounded-control border border-line bg-white text-ink transition-colors hover:bg-page"
    >
      {children}
    </button>
  )
}

function ViewerMessage({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-[520px] w-[380px] items-center justify-center bg-white text-sm text-ink-subtle">
      {children}
    </div>
  )
}

function ThumbSkeleton() {
  return <span className="block h-[60px] w-full animate-pulse bg-page" />
}
