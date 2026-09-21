import { CaretRight } from './icons'

interface AppHeaderProps {
  /** Bold label beside the numbered marker, e.g. "Review & verify". */
  stage: string
  /** Which of Upload / Review / Save is current. */
  step: 1 | 2 | 3
}

const STEPS = ['Upload', 'Review', 'Save']

export function AppHeader({ stage, step }: AppHeaderProps) {
  return (
    <header className="flex h-header shrink-0 items-center gap-3 border-b border-line bg-white px-4 xl:px-8">
      <div className="flex min-w-0 items-center gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] bg-navy text-[13px] font-bold tracking-wide text-white">
          CE
        </span>
        <span className="min-w-0 leading-tight">
          <span className="block truncate text-md font-semibold text-ink">Claim Extractor</span>
          <span className="hidden truncate text-sm text-ink-subtle sm:block">
            Internal expense claim portal
          </span>
        </span>
      </div>

      <div className="ml-auto flex shrink-0 items-center gap-4">
        <div className="flex items-center gap-2.5">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-navy text-xs font-semibold text-white">
            {step}
          </span>
          <span className="hidden text-md font-semibold text-ink md:inline">{stage}</span>
        </div>

        <span className="hidden h-5 w-px bg-line lg:block" aria-hidden="true" />

        <nav className="hidden items-center gap-1.5 text-md text-ink-subtle lg:flex" aria-label="Progress">
          {STEPS.map((label, index) => (
            <span key={label} className="flex items-center gap-1.5">
              <span className={index + 1 === step ? 'font-semibold text-ink' : undefined}>
                {label}
              </span>
              {index < STEPS.length - 1 && <CaretRight size={13} className="text-line" />}
            </span>
          ))}
        </nav>

        <button
          type="button"
          className="focus-ring hidden h-10 items-center gap-1.5 rounded-control border border-line bg-white px-4 text-md text-ink hover:bg-page sm:inline-flex"
        >
          <span className="text-ink-subtle">?</span>
          Help
        </button>

        <span className="inline-flex h-10 items-center gap-2 rounded-control bg-navy-soft pl-1.5 pr-1.5 sm:pr-3.5">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-navy text-[11px] font-semibold text-white">
            AR
          </span>
          <span className="hidden text-md font-medium text-navy sm:inline">A. Rao</span>
        </span>
      </div>
    </header>
  )
}
