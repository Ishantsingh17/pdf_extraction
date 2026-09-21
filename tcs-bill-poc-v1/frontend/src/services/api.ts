import type {
  ApiError,
  ExtractionResult,
  SaveResponse,
  UploadResponse,
} from '../types'

const BASE = '/api/v1'

export class ApiRequestError extends Error {
  code: string

  constructor(error: ApiError) {
    super(error.message)
    this.code = error.code
  }
}

async function unwrap<T>(response: Response): Promise<T> {
  if (response.ok) return (await response.json()) as T

  let detail: ApiError = {
    code: 'server_error',
    message: 'Something went wrong. Please try again.',
  }
  try {
    const body = await response.json()
    if (body?.detail?.code) detail = body.detail as ApiError
    else if (typeof body?.detail === 'string') detail = { code: 'error', message: body.detail }
  } catch {
    /* keep the default message */
  }
  throw new ApiRequestError(detail)
}

export const api = {
  /** Client-side guard so the error states in the reference screens can be
   *  shown before a large file is sent over the wire. */
  maxFileBytes: 10 * 1024 * 1024,
  allowedTypes: ['pdf', 'jpg', 'jpeg', 'png'],

  async upload(file: File, claimHead: string): Promise<UploadResponse> {
    const form = new FormData()
    form.append('file', file)
    form.append('claim_head', claimHead)
    return unwrap<UploadResponse>(
      await fetch(`${BASE}/documents`, { method: 'POST', body: form }),
    )
  },

  async result(documentId: string): Promise<ExtractionResult> {
    return unwrap<ExtractionResult>(await fetch(`${BASE}/documents/${documentId}/result`))
  },

  async patch(
    documentId: string,
    fields: { name: string; value: string | null }[],
  ): Promise<ExtractionResult> {
    return unwrap<ExtractionResult>(
      await fetch(`${BASE}/documents/${documentId}/result`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fields }),
      }),
    )
  },

  async save(documentId: string): Promise<SaveResponse> {
    return unwrap<SaveResponse>(
      await fetch(`${BASE}/documents/${documentId}/save`, { method: 'POST' }),
    )
  },

  previewUrl(documentId: string): string {
    return `${BASE}/documents/${documentId}/preview`
  },
}
