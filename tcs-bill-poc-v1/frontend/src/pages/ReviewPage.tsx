import { useCallback, useMemo, useRef, useState } from 'react'

import { DocumentViewer } from '../components/DocumentViewer'
import { ExtractedDetailsPanel } from '../components/ExtractedDetailsPanel'
import { HomeIcon } from '../components/icons'
import { api } from '../services/api'
import type { ExtractedField, ExtractionResult, SaveResponse } from '../types'

interface ReviewPageProps {
  result: ExtractionResult
  onResult: (result: ExtractionResult) => void
  onSaved: (response: SaveResponse) => void
}

const STATUS_CHIP = {
  Draft: 'bg-navy-soft text-navy',
  Ready: 'bg-ok-bg text-ok',
  issue: 'bg-bad-bg text-bad',
  missing: 'bg-warn-bg text-warn',
} as const

/** Open on the field that most needs attention, so its source is highlighted. */
function initialField(result: ExtractionResult): string | null {
  const attention = result.fields.find(
    (field) => field.status === 'not_found' || field.status === 'needs_review',
  )
  const first = result.fields.find((field) => !field.system_filled)
  return (attention ?? first)?.name ?? null
}

export function ReviewPage({ result, onResult, onSaved }: ReviewPageProps) {
  const [selectedField, setSelectedField] = useState<string | null>(() => initialField(result))
  const [mobileView, setMobileView] = useState<'bill' | 'data'>('data')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const original = useRef(result)

  const selected = useMemo(
    () => result.fields.find((field) => field.name === selectedField) ?? null,
    [result.fields, selectedField],
  )

  const handleSelect = useCallback((field: ExtractedField) => {
    setSelectedField(field.name)
  }, [])

  const handleCommit = useCallback(
    async (name: string, value: string) => {
      try {
        const updated = await api.patch(result.document.id, [{ name, value }])
        onResult(updated)
      } catch (error) {
        setSaveError(error instanceof Error ? error.message : 'Could not save that change.')
      }
    },
    [onResult, result.document.id],
  )

  const handleReset = useCallback(async () => {
    const restore = original.current.fields
      .filter((field) => !field.system_filled)
      .map((field) => ({ name: field.name, value: field.value }))
    const updated = await api.patch(result.document.id, restore)
    onResult(updated)
  }, [onResult, result.document.id])

  const handleReviewIssues = useCallback(() => {
    const issue = result.fields.find(
      (field) => field.status === 'not_found' || field.status === 'needs_review',
    )
    if (issue) {
      setSelectedField(issue.name)
      window.document.getElementById(`field-${issue.name}`)?.focus()
    }
  }, [result.fields])

  const handleSave = useCallback(async () => {
    setSaving(true)
    setSaveError(null)
    try {
      onSaved(await api.save(result.document.id))
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : 'Could not save this claim.')
    } finally {
      setSaving(false)
    }
  }, [onSaved, result.document.id])

  const { chipLabel, chipTone } = useMemo(() => {
    const { summary, claim } = result
    if (summary.not_found > 0)
      return {
        chipLabel: `${summary.not_found} field${summary.not_found > 1 ? 's' : ''} missing`,
        chipTone: STATUS_CHIP.missing,
      }
    if (summary.needs_review >= 2)
      return { chipLabel: `${summary.needs_review} fields need review`, chipTone: STATUS_CHIP.issue }
    if (summary.tone === 'ready' && claim.status !== 'extracted')
      return { chipLabel: 'Ready', chipTone: STATUS_CHIP.Ready }
    if (summary.tone === 'ready') return { chipLabel: 'Ready', chipTone: STATUS_CHIP.Ready }
    return { chipLabel: 'Draft', chipTone: STATUS_CHIP.Draft }
  }, [result])

  const documentMeta = [
    result.document.filename,
    result.document.file_type === 'pdf'
      ? `${result.document.page_count} page${result.document.page_count > 1 ? 's' : ''}`
      : result.document.file_type.toUpperCase(),
    result.currency_note,
  ]
    .filter(Boolean)
    .join(' · ')

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* Claim context bar */}
      <div className="flex h-subbar shrink-0 items-center gap-3 border-b border-line bg-white px-4 xl:px-8">
        <span className="hidden items-center gap-1.5 text-base text-ink-subtle sm:inline-flex">
          <HomeIcon size={14} />
          All claims
        </span>
        <span className="truncate text-base font-bold text-ink">
          {result.claim.claim_reference} · {result.claim.claim_head_label}
        </span>
        <span className={`shrink-0 rounded-md px-2 py-1 text-xs font-semibold ${chipTone}`}>
          {chipLabel}
        </span>
        <span className="ml-auto hidden truncate text-base text-ink-subtle lg:inline">
          {documentMeta}
        </span>
      </div>

      {/* Below the split-screen breakpoint the two halves become tabs
          (02_ui_ux_flow.md section 17). */}
      <div className="flex shrink-0 gap-2 px-4 pt-3 lg:hidden">
        {(['bill', 'data'] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setMobileView(tab)}
            aria-pressed={mobileView === tab}
            className={`h-9 flex-1 rounded-control border text-base font-medium transition-colors ${
              mobileView === tab
                ? 'border-navy bg-navy-soft text-navy'
                : 'border-line bg-white text-ink-muted'
            }`}
          >
            {tab === 'bill' ? 'Bill' : 'Extracted Data'}
          </button>
        ))}
      </div>

      {/* Split screen: real document | extracted fields */}
      <div className="grid min-h-0 flex-1 gap-4 px-4 pb-[17px] pt-4 lg:grid-cols-[minmax(0,1fr)_minmax(380px,420px)] xl:grid-cols-[780px_minmax(0,1fr)] xl:px-8">
        <div
          className={`min-h-0 flex-col ${mobileView === 'bill' ? 'flex' : 'hidden'} lg:flex`}
        >
          <DocumentViewer
            document={result.document}
            activeSource={selected?.source ?? null}
            activeLabel={selected?.label ?? null}
          />
        </div>
        <div
          className={`min-h-0 flex-col ${mobileView === 'data' ? 'flex' : 'hidden'} lg:flex`}
        >
          <ExtractedDetailsPanel
            result={result}
            selectedField={selectedField}
            saving={saving}
            onSelectField={handleSelect}
            onFieldChange={() => undefined}
            onFieldCommit={handleCommit}
            onSave={handleSave}
            onReset={handleReset}
            onReviewIssues={handleReviewIssues}
          />
          {saveError ? (
            <p className="mt-1.5 rounded-control bg-bad-bg px-4 py-1.5 text-sm text-bad">
              {saveError}
            </p>
          ) : (
            <p className="mt-1.5 text-center text-base text-ink-subtle">
              {result.summary.needs_review >= 2
                ? 'We never block saving — review is recommended, not forced.'
                : 'Tip: click any field to jump to its source in the bill.'}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
