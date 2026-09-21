export type ClaimHeadKey = 'TRAVEL_CONVEYANCE' | 'FOOD'

export type FieldStatus = 'high' | 'review' | 'needs_review' | 'not_found'
export type ValidationStatus = 'valid' | 'invalid' | 'not_found' | 'review'
export type SummaryTone = 'ready' | 'review' | 'issue'

/** Where a value came from in the original uploaded document. */
export interface SourceRef {
  page: number
  /** x0, y0, x1, y1 in the page's own coordinate space. */
  bbox: [number, number, number, number] | number[]
  text: string | null
  anchor: string | null
}

export interface CandidateRef {
  value: string
  page: number
  bbox: number[]
  text: string | null
  anchor: string | null
}

export interface ExtractedField {
  name: string
  label: string
  value: string | null
  value_type: 'text' | 'date' | 'money' | 'currency'
  required: boolean
  system_filled: boolean
  confidence: number | null
  status: FieldStatus
  validation: ValidationStatus
  validation_message: string | null
  manually_edited: boolean
  reasons: string[]
  source: SourceRef | null
  candidates: CandidateRef[]
}

export interface DocumentInfo {
  id: string
  filename: string
  file_type: string
  page_count: number
  ocr_used: boolean
  preview_url: string
}

export interface ClaimInfo {
  claim_head: ClaimHeadKey
  claim_head_label: string
  claim_reference: string
  status: string
}

export interface ReviewSummary {
  headline: string
  detail: string
  tone: SummaryTone
  total_fields: number
  extracted_fields: number
  high_confidence: number
  needs_review: number
  not_found: number
}

export interface ProcessingNotice {
  code: string
  message: string
  hint: string | null
}

export interface ExtractionResult {
  document: DocumentInfo
  claim: ClaimInfo
  summary: ReviewSummary
  fields: ExtractedField[]
  remarks: string | null
  currency_note: string | null
  notice: ProcessingNotice | null
}

export interface UploadResponse {
  document_id: string
  status: string
  claim_head: ClaimHeadKey
  claim_reference: string
  page_count: number
  ocr_used: boolean
}

export interface SaveResponse {
  claim_id: string
  claim_reference: string
  status: string
  saved_at: string
  claim_head_label: string
  bill_date: string | null
  bill_amount_display: string | null
  manually_edited_count: number
  json_payload: Record<string, unknown>
}

export interface ApiError {
  code: string
  message: string
}
