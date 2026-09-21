import { useMemo, useState } from 'react'

import type { ExtractedField, ExtractionResult, SummaryTone } from '../types'
import { ExtractedFieldRow } from './ExtractedFieldRow'
import { AlertIcon } from './icons'

interface ExtractedDetailsPanelProps {
  result: ExtractionResult
  selectedField: string | null
  saving: boolean
  onSelectField: (field: ExtractedField) => void
  onFieldChange: (name: string, value: string) => void
  onFieldCommit: (name: string, value: string) => void
  onSave: () => void
  onReset: () => void
  onReviewIssues: () => void
}

const TONES: Record<SummaryTone, { banner: string; dot: string }> = {
  ready: { banner: 'bg-ok-bg', dot: 'bg-ok' },
  review: { banner: 'bg-warn-bg', dot: 'bg-warn' },
  issue: { banner: 'bg-bad-bg', dot: 'bg-bad' },
}

/** Currency and Remarks sit side by side at the foot of the form. */
const PAIRED_FIELDS = ['currency', 'remarks']

export function ExtractedDetailsPanel({
  result,
  selectedField,
  saving,
  onSelectField,
  onFieldChange,
  onFieldCommit,
  onSave,
  onReset,
  onReviewIssues,
}: ExtractedDetailsPanelProps) {
  const [showSummaryDetail, setShowSummaryDetail] = useState(false)
  const tone = TONES[result.summary.tone]

  const { stacked, paired } = useMemo(
    () => ({
      stacked: result.fields.filter((field) => !PAIRED_FIELDS.includes(field.name)),
      paired: result.fields.filter((field) => PAIRED_FIELDS.includes(field.name)),
    }),
    [result.fields],
  )

  const issueCount = result.summary.needs_review + result.summary.not_found
  const missingField = result.fields.find((field) => field.status === 'not_found')

  return (
    <section className="card flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="shrink-0 px-4 pb-[9px] pt-3.5">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold tracking-[-0.01em] text-ink">Extracted Details</h2>
          <a
            href={result.document.preview_url}
            target="_blank"
            rel="noreferrer"
            className="focus-ring text-base font-medium text-navy underline underline-offset-2"
          >
            View original
          </a>
        </div>

        {/* Review summary */}
        <div className={`mt-2 flex items-start gap-3 rounded-control px-4 py-2.5 ${tone.banner}`}>
          <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${tone.dot}`} aria-hidden="true" />
          <div className="min-w-0 flex-1">
            <p className="text-base font-bold text-ink">{result.summary.headline}</p>
            <p className="mt-0.5 text-sm text-ink-muted">{result.summary.detail}</p>
          </div>
          <button
            type="button"
            onClick={() => setShowSummaryDetail((value) => !value)}
            className="focus-ring shrink-0 text-base font-medium text-navy underline underline-offset-2"
          >
            Details
          </button>
        </div>

        {showSummaryDetail && (
          <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 rounded-control border border-line bg-page px-4 py-2.5 text-sm">
            <SummaryStat
              label="Fields extracted"
              value={`${result.summary.extracted_fields} of ${result.summary.total_fields}`}
            />
            <SummaryStat label="High confidence" value={result.summary.high_confidence} />
            <SummaryStat label="Need review" value={result.summary.needs_review} />
            <SummaryStat label="Not found" value={result.summary.not_found} />
            <SummaryStat
              label="Read using"
              value={result.document.ocr_used ? 'Text recognition' : 'Document text'}
            />
          </dl>
        )}

        {/* One explanation is enough: a whole-document failure already says it. */}
        {missingField && !result.notice && (
          <p className="mt-2 rounded-control border border-dashed border-warn bg-white px-4 py-2.5 text-base leading-[21px] text-ink-muted">
            <span className="font-semibold text-ink">
              {missingField.label} was not found in the document.
            </span>{' '}
            We left it blank rather than guessing — you can enter it manually.
          </p>
        )}

        {result.notice && (
          <div className="mt-2 rounded-control bg-bad-bg px-4 py-3">
            <p className="text-base font-bold leading-[21px] text-ink">{result.notice.message}</p>
            {result.notice.hint && (
              <p className="mt-1 text-sm text-ink-muted">{result.notice.hint}</p>
            )}
          </div>
        )}
      </div>

      {/* Fields - the only scrolling region of the panel */}
      <div className="min-h-0 flex-1 overflow-y-auto border-t border-line px-4 pb-4 pt-[7px]">
        <p className="text-[12.5px] font-semibold leading-[18px] text-ink-muted">Claim Head</p>
        <div className="relative mt-1.5">
          <input
            readOnly
            value={result.claim.claim_head_label}
            aria-label="Claim head"
            className="field-input cursor-default bg-page pr-20 font-medium"
          />
          <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-base text-ink-subtle">
            locked
          </span>
        </div>

        <div className="mt-[11px] space-y-[11px]">
          {stacked.map((field) => (
            <ExtractedFieldRow
              key={field.name}
              field={field}
              selected={selectedField === field.name}
              onSelect={onSelectField}
              onChange={onFieldChange}
              onCommit={onFieldCommit}
            />
          ))}

          {paired.length > 0 && (
            <div className="grid grid-cols-2 gap-[11px]">
              {paired.map((field) => (
                <ExtractedFieldRow
                  key={field.name}
                  field={field}
                  selected={selectedField === field.name}
                  onSelect={onSelectField}
                  onChange={onFieldChange}
                  onCommit={onFieldCommit}
                />
              ))}
            </div>
          )}
        </div>

        <div className="mt-3.5 flex flex-wrap items-center gap-2">
          <LegendChip className="border-line text-ink-muted" dot="bg-ok" label="extracted" />
          <LegendChip className="border-line text-ink-muted" dot="bg-warn" label="needs review" />
          <LegendChip className="border-warn text-warn" dot="bg-warn" label="not found" />
          <LegendChip className="border-navy text-navy" dot="bg-navy" label="manual" />
        </div>
      </div>

      {/* Sticky actions - the emphasis follows how much review is outstanding */}
      <div className="shrink-0 border-t border-line bg-white px-4 pb-[13px] pt-3.5">
        <div className="flex items-center gap-3">
          {missingField ? (
            <button type="button" onClick={onReviewIssues} className="btn-ghost flex-1">
              Skip for now
            </button>
          ) : result.summary.needs_review >= 2 ? (
            <button type="button" onClick={onReviewIssues} className="btn-dark flex-1 gap-2">
              <AlertIcon size={15} />
              Review Issues ({issueCount})
            </button>
          ) : issueCount > 0 ? (
            <>
              <button type="button" onClick={onReviewIssues} className="btn-ghost flex-1">
                Review Issues ({issueCount})
              </button>
              <button type="button" onClick={onReset} className="btn-ghost flex-1">
                Reset
              </button>
            </>
          ) : (
            <button type="button" onClick={onReset} className="btn-ghost flex-1">
              Reset Changes
            </button>
          )}
          <button type="button" onClick={onSave} disabled={saving} className="btn-primary flex-1">
            {saving ? 'Saving…' : 'Save Claim'}
          </button>
        </div>
      </div>
    </section>
  )
}

function SummaryStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-ink-subtle">{label}</dt>
      <dd className="font-semibold tabular-nums text-ink">{value}</dd>
    </div>
  )
}

function LegendChip({ label, dot, className }: { label: string; dot: string; className: string }) {
  return (
    <span
      className={`inline-flex h-[22px] items-center gap-1.5 rounded-md border bg-white px-2 text-xs ${className}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} aria-hidden="true" />
      {label}
    </span>
  )
}
