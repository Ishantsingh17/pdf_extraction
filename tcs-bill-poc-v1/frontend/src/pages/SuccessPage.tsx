import { useState } from 'react'

import { CheckIcon } from '../components/icons'
import type { SaveResponse } from '../types'

interface SuccessPageProps {
  saved: SaveResponse
  onUploadAnother: () => void
}

export function SuccessPage({ saved, onUploadAnother }: SuccessPageProps) {
  const [showJson, setShowJson] = useState(false)

  const editedNote =
    saved.manually_edited_count > 0
      ? `${saved.manually_edited_count} field${saved.manually_edited_count > 1 ? 's' : ''} manually edited`
      : 'no manual edits'

  return (
    <main className="flex flex-1 flex-col items-center px-4 pt-14 text-center">
      <span className="flex h-16 w-16 items-center justify-center rounded-full bg-ok text-white">
        <CheckIcon size={30} strokeWidth={2.2} />
      </span>

      <h1 className="mt-5 text-[26px] font-bold leading-[32px] tracking-[-0.02em] text-ink">
        Claim details saved
      </h1>
      <p className="mt-2 text-md text-ink-muted">
        Your extracted claim information has been saved successfully.
      </p>

      <section className="card mt-[23px] w-full max-w-[496px] overflow-hidden text-left">
        <div className="flex h-[52px] items-center justify-between px-5">
          <span className="text-md font-bold text-ink">{saved.claim_reference}</span>
          <span className="inline-flex items-center gap-1.5 rounded-md bg-ok-bg px-2.5 py-1 text-xs font-semibold text-ok">
            <CheckIcon size={12} />
            Saved · just now
          </span>
        </div>

        <dl className="grid grid-cols-3 border-y border-line">
          <Cell label="Claim Head" value={saved.claim_head_label} />
          <Cell label="Bill Date" value={saved.bill_date ?? '—'} bordered />
          <Cell label="Bill Amount" value={saved.bill_amount_display ?? '—'} bordered />
        </dl>

        <p className="px-5 py-[13px] text-center text-base text-ink-subtle">
          Verified against original bill · {editedNote} · audit trail kept
        </p>
      </section>

      <div className="mt-6 flex w-full max-w-[496px] items-center gap-3">
        <button
          type="button"
          onClick={() => setShowJson((value) => !value)}
          className="btn-ghost h-[46px] w-full max-w-[242px] flex-1"
        >
          View Claim
        </button>
        <button type="button" onClick={onUploadAnother} className="btn-primary h-[46px] w-full max-w-[242px] flex-1">
          + Upload Another Bill
        </button>
      </div>

      <button
        type="button"
        onClick={onUploadAnother}
        className="focus-ring mt-4 text-md font-medium text-navy underline underline-offset-2"
      >
        Back to my claims
      </button>

      {showJson && (
        <pre className="mt-6 max-h-[320px] w-full max-w-[642px] overflow-auto rounded-card border border-line bg-white p-5 text-left text-xs leading-relaxed text-ink-muted">
          {JSON.stringify(saved.json_payload, null, 2)}
        </pre>
      )}
    </main>
  )
}

function Cell({ label, value, bordered }: { label: string; value: string; bordered?: boolean }) {
  return (
    <div className={`px-5 py-[15px] ${bordered ? 'border-l border-line' : ''}`}>
      <dt className="text-base text-ink-subtle">{label}</dt>
      <dd className="mt-1 text-md font-bold leading-snug text-ink">{value}</dd>
    </div>
  )
}
