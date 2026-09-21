import type { ExtractedField, FieldStatus } from '../types'
import { AlertIcon, CheckIcon, InfoIcon } from './icons'

/**
 * Confidence UX from 02_ui_ux_flow.md section 10: the human-readable status
 * leads, the number is secondary.
 */
const PRESETS: Record<
  FieldStatus,
  { label: string; className: string; dot: string; Icon: typeof CheckIcon }
> = {
  high: {
    label: 'High confidence',
    className: 'bg-ok-bg text-ok',
    dot: 'bg-ok',
    Icon: CheckIcon,
  },
  review: {
    label: 'Review suggested',
    className: 'bg-warn-bg text-warn',
    dot: 'bg-warn',
    Icon: InfoIcon,
  },
  needs_review: {
    label: 'Needs review',
    className: 'bg-bad-bg text-bad',
    dot: 'bg-bad',
    Icon: AlertIcon,
  },
  not_found: {
    label: 'Not found in document',
    className: 'bg-warn-bg text-warn',
    dot: 'bg-warn',
    Icon: AlertIcon,
  },
}

export function ConfidenceBadge({ field }: { field: ExtractedField }) {
  const preset = PRESETS[field.status]
  const percent =
    field.status !== 'not_found' && field.confidence !== null
      ? ` · ${Math.round(field.confidence * 100)}%`
      : ''

  return (
    <span
      className={`inline-flex h-5 items-center gap-1.5 rounded-md px-2 text-xs font-semibold ${preset.className}`}
    >
      {field.status === 'not_found' ? (
        <preset.Icon size={12} />
      ) : (
        <>
          <span className={`h-1.5 w-1.5 rounded-full ${preset.dot}`} aria-hidden="true" />
          <preset.Icon size={12} />
        </>
      )}
      {preset.label}
      {percent}
    </span>
  )
}

/**
 * "Why 94%?" popover - plain-language evidence only, never feature weights
 * (02_ui_ux_flow.md section 11).
 */
export function ConfidenceDetails({ field }: { field: ExtractedField }) {
  const percent = field.confidence !== null ? Math.round(field.confidence * 100) : null

  return (
    <div className="mt-2.5 rounded-control border border-line bg-page px-3.5 py-3">
      <p className="text-base font-semibold text-ink">
        {percent !== null ? `Why ${percent}% confidence?` : 'What we found'}
      </p>
      <ul className="mt-1.5 space-y-1">
        {field.reasons.length > 0 ? (
          field.reasons.map((reason) => (
            <li key={reason} className="flex items-start gap-1.5 text-sm text-ink-muted">
              <CheckIcon size={13} className="mt-0.5 shrink-0 text-ok" />
              {reason}
            </li>
          ))
        ) : (
          <li className="text-sm text-ink-muted">No strong supporting evidence was found.</li>
        )}
      </ul>
      {field.source && (
        <p className="mt-2.5 border-t border-line pt-2.5 text-sm text-ink-subtle">
          Source: Page {field.source.page}
          {field.source.anchor ? ` · near “${field.source.anchor}”` : ''}
        </p>
      )}
    </div>
  )
}
