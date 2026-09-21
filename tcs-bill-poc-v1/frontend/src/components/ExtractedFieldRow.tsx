import { useEffect, useRef, useState } from 'react'

import type { ExtractedField } from '../types'
import { ConfidenceBadge, ConfidenceDetails } from './ConfidenceBadge'
import { LinkIcon } from './icons'

interface ExtractedFieldRowProps {
  field: ExtractedField
  selected: boolean
  onSelect: (field: ExtractedField) => void
  onChange: (name: string, value: string) => void
  onCommit: (name: string, value: string) => void
}

export function ExtractedFieldRow({
  field,
  selected,
  onSelect,
  onChange,
  onCommit,
}: ExtractedFieldRowProps) {
  const [showWhy, setShowWhy] = useState(false)
  const [draft, setDraft] = useState(field.value ?? '')
  const dirty = useRef(false)

  // Keep in step with server state unless the user is mid-edit.
  useEffect(() => {
    if (!dirty.current) setDraft(field.value ?? '')
  }, [field.value])

  const notFound = field.status === 'not_found'
  const locked = field.name === 'claim_head'
  const hasSource = Boolean(field.source)

  // Amounts are shown with the currency the bill printed, so the alternatives
  // have to carry it too - otherwise picking one would drop it.
  const currencyPrefix =
    field.value_type === 'money' ? (field.value?.match(/^([^\d\s]+|[A-Z]{3})\s/)?.[1] ?? '') : ''
  const withPrefix = (value: string) =>
    currencyPrefix && !/[A-Za-z$€£¥₹]/.test(value) ? `${currencyPrefix} ${value}` : value

  // Distinct runner-up values worth showing the user as a choice.
  const alternatives =
    field.status === 'high' || field.manually_edited
      ? []
      : field.candidates
          .map((candidate) => ({ ...candidate, value: withPrefix(candidate.value) }))
          .filter(
            (candidate, index, all) =>
              all.findIndex((other) => other.value === candidate.value) === index,
          )

  const commit = () => {
    dirty.current = false
    if ((field.value ?? '') !== draft) onCommit(field.name, draft)
  }

  return (
    <div
      onClick={() => onSelect(field)}
      className={`rounded-control border bg-white px-2.5 pb-[9px] pt-3 transition-colors ${
        selected ? 'border-navy ring-1 ring-navy' : 'border-line hover:border-navy-border'
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <label
          htmlFor={`field-${field.name}`}
          className="text-[12.5px] font-semibold leading-[18px] text-ink-muted"
        >
          {field.label}
        </label>
        {field.manually_edited && (
          <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-navy">
            <span className="h-1.5 w-1.5 rounded-full bg-navy" aria-hidden="true" />
            Manually edited
          </span>
        )}
      </div>

      <div className="relative mt-[3px]">
        <input
          id={`field-${field.name}`}
          value={draft}
          readOnly={field.system_filled}
          placeholder={notFound ? 'Enter value manually' : undefined}
          onFocus={() => onSelect(field)}
          onChange={(event) => {
            dirty.current = true
            setDraft(event.target.value)
            onChange(field.name, event.target.value)
          }}
          onBlur={commit}
          onKeyDown={(event) => {
            if (event.key === 'Enter') event.currentTarget.blur()
          }}
          className={`field-input ${selected && hasSource ? 'pr-[104px]' : ''} ${
            notFound
              ? 'border-dashed border-warn bg-manual placeholder:text-ink-subtle'
              : ''
          } ${field.system_filled ? 'cursor-default bg-white' : ''}`}
        />
        {selected && hasSource && (
          <span className="pointer-events-none absolute right-3 top-1/2 inline-flex -translate-y-1/2 items-center gap-1 text-xs font-medium text-navy">
            <LinkIcon size={12} />
            linked to bill
          </span>
        )}
        {locked && (
          <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-base text-ink-subtle">
            locked
          </span>
        )}
      </div>

      <div className="mt-[7px] flex flex-wrap items-center gap-2.5">
        <ConfidenceBadge field={field} />
        {(field.status === 'review' || field.status === 'needs_review') &&
          field.reasons.length > 0 && (
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation()
                setShowWhy((value) => !value)
              }}
              className="focus-ring text-xs font-semibold text-navy underline underline-offset-2"
            >
              Why?
            </button>
          )}
      </div>

      {/* Conflicting candidates are surfaced, never auto-picked for the user
          (03_app_flow.md section 13). */}
      {alternatives.length > 1 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {alternatives.map((candidate) => {
            const chosen = draft.includes(candidate.value)
            return (
              <button
                key={`${candidate.value}-${candidate.page}`}
                type="button"
                onClick={(event) => {
                  event.stopPropagation()
                  dirty.current = false
                  setDraft(candidate.value)
                  onCommit(field.name, candidate.value)
                }}
                className={`focus-ring rounded-md border bg-white px-2.5 py-1 text-xs transition-colors ${
                  chosen
                    ? 'border-navy font-semibold text-navy'
                    : 'border-line text-ink-muted hover:border-navy-border'
                }`}
              >
                {candidate.value}
                {candidate.anchor ? ` · near “${candidate.anchor}”` : ''}
              </button>
            )
          })}
        </div>
      )}

      {notFound && (
        <p className="mt-1.5 text-sm leading-[18px] text-ink-muted">
          You can enter it manually — it will be marked as manually entered.
        </p>
      )}
      {!notFound && field.validation_message && (
        <p className="mt-1.5 text-sm text-ink-muted">{field.validation_message}</p>
      )}
      {!notFound && !field.validation_message && field.status !== 'high' && (
        <p className="mt-1.5 text-sm text-ink-muted">Please compare this value with the bill.</p>
      )}

      {showWhy && <ConfidenceDetails field={field} />}
    </div>
  )
}
