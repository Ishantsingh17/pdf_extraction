import { useCallback, useState } from 'react'

import { AppHeader } from './components/AppHeader'
import { ProcessingPage } from './pages/ProcessingPage'
import { ReviewPage } from './pages/ReviewPage'
import { SuccessPage } from './pages/SuccessPage'
import { UploadPage } from './pages/UploadPage'
import { ApiRequestError, api } from './services/api'
import type { ApiError, ClaimHeadKey, ExtractionResult, SaveResponse } from './types'

type Screen = 'upload' | 'processing' | 'review' | 'saved'

const CLAIM_HEAD_LABELS: Record<ClaimHeadKey, { label: string; fields: number }> = {
  TRAVEL_CONVEYANCE: { label: 'Travel Conveyance', fields: 7 },
  FOOD: { label: 'Food', fields: 6 },
}

const STAGE_BY_SCREEN: Record<Screen, { stage: string; step: 1 | 2 | 3 }> = {
  upload: { stage: 'Upload bill', step: 1 },
  processing: { stage: 'Extracting details', step: 1 },
  review: { stage: 'Review & verify', step: 2 },
  saved: { stage: 'Saved', step: 3 },
}

export default function App() {
  const [screen, setScreen] = useState<Screen>('upload')
  const [claimHead, setClaimHead] = useState<ClaimHeadKey>('TRAVEL_CONVEYANCE')
  const [pendingFile, setPendingFile] = useState<File | null>(null)
  const [pendingPages, setPendingPages] = useState<number | null>(null)
  const [result, setResult] = useState<ExtractionResult | null>(null)
  const [saved, setSaved] = useState<SaveResponse | null>(null)
  const [error, setError] = useState<ApiError | null>(null)

  const handleSubmit = useCallback(
    async (file: File) => {
      setPendingFile(file)
      setError(null)
      setScreen('processing')

      // The processing screen needs a moment of its own: the pipeline usually
      // finishes faster than the stage list can be read.
      const startedAt = Date.now()
      setPendingPages(null)
      try {
        const upload = await api.upload(file, claimHead)
        setPendingPages(upload.page_count)
        const extraction = await api.result(upload.document_id)
        const elapsed = Date.now() - startedAt
        window.setTimeout(
          () => {
            setResult(extraction)
            setScreen('review')
          },
          Math.max(0, 2600 - elapsed),
        )
      } catch (caught) {
        const apiError: ApiError =
          caught instanceof ApiRequestError
            ? { code: caught.code, message: caught.message }
            : { code: 'network', message: 'We could not reach the extraction service.' }
        setError(apiError)
        setPendingFile(null)
        setScreen('upload')
      }
    },
    [claimHead],
  )

  const restart = useCallback(() => {
    setResult(null)
    setSaved(null)
    setPendingFile(null)
    setPendingPages(null)
    setError(null)
    setScreen('upload')
  }, [])

  const { stage, step } = STAGE_BY_SCREEN[screen]

  return (
    <div className="flex h-full min-h-screen flex-col bg-page">
      <AppHeader stage={stage} step={step} />

      {screen === 'upload' && (
        <UploadPage
          claimHead={claimHead}
          onClaimHeadChange={setClaimHead}
          onSubmit={handleSubmit}
          error={error}
          onDismissError={() => setError(null)}
        />
      )}

      {screen === 'processing' && pendingFile && (
        <ProcessingPage
          fileName={pendingFile.name}
          claimHeadLabel={CLAIM_HEAD_LABELS[claimHead].label}
          fieldCount={CLAIM_HEAD_LABELS[claimHead].fields}
          pageCount={pendingPages}
          onCancel={restart}
        />
      )}

      {screen === 'review' && result && (
        <ReviewPage
          result={result}
          onResult={setResult}
          onSaved={(response) => {
            setSaved(response)
            setScreen('saved')
          }}
        />
      )}

      {screen === 'saved' && saved && (
        <SuccessPage saved={saved} onUploadAnother={restart} />
      )}
    </div>
  )
}
