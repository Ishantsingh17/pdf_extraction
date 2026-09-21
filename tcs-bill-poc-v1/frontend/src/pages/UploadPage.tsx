import { useRef, useState } from 'react'

import { api } from '../services/api'
import type { ClaimHeadKey } from '../types'
import { ArrowRightIcon, FileTypeTile, UploadCloudIcon } from '../components/icons'

interface UploadPageProps {
  claimHead: ClaimHeadKey
  onClaimHeadChange: (value: ClaimHeadKey) => void
  onSubmit: (file: File) => void
  /** Error surfaced by a rejected upload, so the user stays on this screen. */
  error: { code: string; message: string } | null
  onDismissError: () => void
}

const CLAIM_HEADS: { key: ClaimHeadKey; label: string; fields: string; summary: string }[] = [
  {
    key: 'TRAVEL_CONVEYANCE',
    label: 'Travel Conveyance',
    fields: '7 fields',
    summary: 'From, To, Bill Date, Bill No., Currency, Amount, Remarks. Nothing else is read or stored.',
  },
  {
    key: 'FOOD',
    label: 'Food',
    fields: '6 fields',
    summary: 'Hotel Name, Bill Date, Bill No., Currency, Amount, Remarks. Nothing else is read or stored.',
  },
]

const STEPS = [
  'Upload + select claim head',
  'We extract only required fields',
  'Verify against the real bill & save',
]

function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${Math.max(1, Math.round(bytes / 1024))} KB`
}

function extensionOf(name: string): string {
  return name.split('.').pop()?.toLowerCase() ?? ''
}

export function UploadPage({
  claimHead,
  onClaimHeadChange,
  onSubmit,
  error,
  onDismissError,
}: UploadPageProps) {
  const [file, setFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const active = CLAIM_HEADS.find((entry) => entry.key === claimHead) ?? CLAIM_HEADS[0]
  const extension = file ? extensionOf(file.name) : ''
  const unsupported = Boolean(file) && !api.allowedTypes.includes(extension)
  const tooLarge = Boolean(file) && (file?.size ?? 0) > api.maxFileBytes
  const blocked = unsupported || tooLarge

  const pickFile = (next: File | null) => {
    onDismissError()
    setFile(next)
  }

  return (
    <main className="mx-auto w-full max-w-[914px] px-4 pb-16 pt-10 xl:px-0">
      <nav className="flex items-center gap-2.5 text-base" aria-label="Progress">
        <span className="font-semibold text-navy">1 · Upload</span>
        <span className="text-line">—</span>
        <span className="text-ink-subtle">2 · Review</span>
        <span className="text-line">—</span>
        <span className="text-ink-subtle">3 · Save</span>
      </nav>

      <h1 className="mt-2 text-3xl font-bold tracking-[-0.03em] text-ink">Submit a Bill</h1>
      <p className="mt-2 text-lg text-ink-muted">
        Upload a bill and we&apos;ll extract the information required for your claim.
      </p>

      <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px] xl:grid-cols-[550px_340px]">
        {/* Upload card */}
        <section className="card p-6">
          <h2 className="text-md font-semibold text-ink">Claim Head</h2>

          <div className="relative mt-2.5">
            <select
              value={claimHead}
              onChange={(event) => onClaimHeadChange(event.target.value as ClaimHeadKey)}
              className="field-input h-[42px] appearance-none pr-10 text-md"
              aria-label="Claim head"
            >
              {CLAIM_HEADS.map((entry) => (
                <option key={entry.key} value={entry.key}>
                  {entry.label}
                </option>
              ))}
            </select>
            <span className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-ink-subtle">
              ▾
            </span>
          </div>

          <div className="mt-2 flex items-center gap-2">
            {CLAIM_HEADS.map((entry) => (
              <button
                key={entry.key}
                type="button"
                onClick={() => onClaimHeadChange(entry.key)}
                aria-pressed={entry.key === claimHead}
                className={`focus-ring h-[26px] rounded-md border px-2.5 text-sm transition-colors ${
                  entry.key === claimHead
                    ? 'border-transparent bg-navy-soft font-semibold text-navy'
                    : 'border-line bg-white text-ink-muted hover:bg-page'
                }`}
              >
                {entry.label}
              </button>
            ))}
          </div>

          {/* Drop zone */}
          <div
            onDragOver={(event) => {
              event.preventDefault()
              setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault()
              setDragging(false)
              const dropped = event.dataTransfer.files?.[0]
              if (dropped) pickFile(dropped)
            }}
            className={`mt-5 flex min-h-[254px] flex-col items-center justify-center rounded-card border-2 border-dashed px-6 py-7 text-center transition-colors ${
              blocked
                ? 'border-bad bg-bad-tint'
                : dragging
                  ? 'border-navy bg-navy-soft/50'
                  : 'border-line bg-page'
            }`}
          >
            {blocked ? (
              <>
                <FileTypeTile type={extension.slice(0, 3) || 'file'} />
                <p className="mt-3.5 text-lg font-bold text-ink">{file?.name}</p>
                <p className="mt-1.5 text-md font-semibold text-bad">
                  {tooLarge ? 'This file is too large.' : "This file format isn't supported."}
                </p>
                <p className="mt-1 text-md text-ink-muted">
                  {tooLarge
                    ? 'Please upload a smaller document — try compressing or splitting the PDF.'
                    : 'Please upload a PDF, JPG, JPEG, or PNG.'}
                </p>
                <button
                  type="button"
                  onClick={() => inputRef.current?.click()}
                  className="btn-dark mt-4 h-10"
                >
                  Choose a different file
                </button>
              </>
            ) : (
              <>
                <span className="flex h-[41px] w-[41px] items-center justify-center rounded-full bg-navy-soft text-navy">
                  <UploadCloudIcon size={20} />
                </span>
                <p className="mt-[18px] text-lg font-bold text-ink">Drop your bill here</p>
                <p className="mt-1 text-base text-ink-subtle">or</p>
                <button
                  type="button"
                  onClick={() => inputRef.current?.click()}
                  className="btn-primary mt-2.5 h-9 px-6"
                >
                  Browse files
                </button>
                <p className="mt-2.5 text-base text-ink-subtle">
                  PDF, JPG, JPEG, PNG · max 10 MB
                </p>
              </>
            )}
            <input
              ref={inputRef}
              type="file"
              accept=".pdf,.jpg,.jpeg,.png"
              className="sr-only"
              onChange={(event) => pickFile(event.target.files?.[0] ?? null)}
            />
          </div>

          {/* Selected file */}
          {file && !blocked && (
            <div className="mt-[18px] flex h-[65px] items-center gap-3 rounded-control border border-line px-4">
              <FileTypeTile type={extension} />
              <span className="min-w-0 flex-1 leading-tight">
                <span className="block truncate text-md font-semibold text-ink">{file.name}</span>
                <span className="block text-base text-ink-subtle">
                  {extension.toUpperCase()} · {formatSize(file.size)}
                </span>
              </span>
              <button
                type="button"
                onClick={() => inputRef.current?.click()}
                className="focus-ring text-md font-medium text-ink underline underline-offset-2"
              >
                Change
              </button>
              <button
                type="button"
                onClick={() => pickFile(null)}
                className="focus-ring text-md font-medium text-ink-muted underline underline-offset-2"
              >
                Remove
              </button>
            </div>
          )}

          {error && (
            <p className="mt-4 rounded-control bg-bad-bg px-4 py-3 text-md text-bad">
              {error.message}
            </p>
          )}

          <button
            type="button"
            disabled={!file || blocked}
            onClick={() => file && onSubmit(file)}
            className="btn-primary mt-5 h-11 w-full gap-2"
          >
            Extract Bill
            <ArrowRightIcon size={16} />
          </button>
          <p className="mt-3 text-center text-base text-ink-subtle">
            Extraction takes ~20 seconds. Your file never leaves your network.
          </p>
        </section>

        {/* Side rail */}
        <aside className="space-y-4">
          <section className="rounded-card bg-ink px-5 py-[18px] text-white">
            <h2 className="text-md font-bold">How it works</h2>
            <ol className="mt-3.5 space-y-3">
              {STEPS.map((step, index) => (
                <li key={step} className="flex items-center gap-3">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-white/10 text-xs font-semibold">
                    {index + 1}
                  </span>
                  <span className="text-base text-white/90">{step}</span>
                </li>
              ))}
            </ol>
          </section>

          <section className="card px-5 pb-5 pt-4">
            <h2 className="text-md font-bold text-ink">What gets extracted?</h2>
            <span className="mt-1.5 inline-flex h-[27px] items-center rounded-md bg-navy-soft px-2.5 text-sm font-semibold text-navy">
              {active.label} · {active.fields}
            </span>
            <p className="mt-1.5 text-base leading-[21px] text-ink-muted">{active.summary}</p>
            <p className="mt-[30px] border-t border-line pt-4 text-base text-ink-subtle">
              SOC2 · ISO 27001 · On-prem processing
            </p>
          </section>
        </aside>
      </div>
    </main>
  )
}
