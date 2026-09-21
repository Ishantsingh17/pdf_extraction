import { useEffect, useState } from 'react'

import { FileTypeTile } from '../components/icons'

interface ProcessingPageProps {
  fileName: string
  claimHeadLabel: string
  fieldCount: number
  /** Known once the upload has been accepted; null while it is still in flight. */
  pageCount: number | null
  onCancel: () => void
}

interface Stage {
  title: string
  detail: (context: { pageCount: number | null; fieldCount: number; claimHead: string }) => string
}

/** User-facing labels only - no OCR/model terminology (UI/UX section 5). */
const STAGES: Stage[] = [
  { title: 'Uploading bill', detail: () => 'File received securely' },
  {
    title: 'Reading document',
    detail: ({ pageCount }) =>
      pageCount ? `${pageCount} page${pageCount > 1 ? 's' : ''} detected` : 'Checking the document',
  },
  { title: 'Analyzing bill layout', detail: () => 'Locating totals, dates & route…' },
  {
    title: 'Extracting required information',
    detail: ({ fieldCount, claimHead }) => `${fieldCount} fields for ${claimHead}`,
  },
  { title: 'Validating details', detail: () => 'Checking formats & confidence' },
]

export function ProcessingPage({
  fileName,
  claimHeadLabel,
  fieldCount,
  pageCount,
  onCancel,
}: ProcessingPageProps) {
  const [stage, setStage] = useState(0)

  // The pipeline runs server-side; this paces the visible stages so the user
  // can see what is happening rather than watching a bare spinner.
  useEffect(() => {
    const timer = window.setInterval(() => {
      setStage((current) => (current >= STAGES.length - 1 ? current : current + 1))
    }, 800)
    return () => window.clearInterval(timer)
  }, [])

  const extension = fileName.split('.').pop()?.toLowerCase() ?? 'pdf'
  const progress = ((stage + 1) / STAGES.length) * 100
  const context = { pageCount, fieldCount, claimHead: claimHeadLabel }

  return (
    <main className="flex flex-1 flex-col items-center px-4 pt-11 text-center">
      <div className="inline-flex items-center gap-3 rounded-card border border-line bg-white px-4 py-3 shadow-card">
        <FileTypeTile type={extension} />
        <span className="text-md font-semibold text-ink">{fileName}</span>
        <span className="text-md text-ink-subtle">· {claimHeadLabel}</span>
      </div>

      <h1 className="mt-[22px] text-2xl font-bold tracking-[-0.02em] text-ink">
        We&apos;re extracting the information needed for your claim.
      </h1>
      <p className="mt-2.5 text-md text-ink-muted">
        Hold on — this usually takes about 20 seconds.
      </p>

      <section className="card mt-[22px] w-full max-w-[694px] p-6 text-left">
        <div className="h-1.5 w-full overflow-hidden rounded-pill bg-page">
          <div
            className="h-full rounded-pill bg-navy transition-[width] duration-700 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>

        <ol className="mt-4 space-y-4">
          {STAGES.map((entry, index) => {
            const done = index < stage
            const current = index === stage

            return (
              <li key={entry.title} className="relative flex gap-[21px]">
                {index < STAGES.length - 1 && (
                  <span
                    className="absolute left-[7px] top-[24px] h-[calc(100%+4px)] w-px bg-line"
                    aria-hidden="true"
                  />
                )}
                <span
                  className={`relative z-10 mt-1 h-4 w-4 shrink-0 rounded-full ${
                    done ? 'bg-ok' : current ? 'bg-navy' : 'bg-page ring-1 ring-line'
                  }`}
                  aria-hidden="true"
                />
                <span className="pt-px">
                  <span
                    className={`block text-md font-semibold leading-[18px] ${
                      done || current ? 'text-ink' : 'text-ink-subtle'
                    }`}
                  >
                    {entry.title}
                  </span>
                  <span className="block text-base leading-[18px] text-ink-subtle">
                    {entry.detail(context)}
                  </span>
                </span>
              </li>
            )
          })}
        </ol>
      </section>

      <div className="mt-8 flex items-center gap-3">
        <button type="button" onClick={onCancel} className="btn-ghost h-11 px-7">
          Cancel
        </button>
        <button type="button" disabled className="btn h-11 bg-page px-7 text-ink-subtle">
          Upload in background
        </button>
      </div>
    </main>
  )
}
