import type {
  AnalysisOut,
  Insights,
  ApplicationStatus,
  JobOut,
  JobSummary,
  ProfileData,
  ProfileDraft,
  ProfileOut,
  TextOut,
  TextRequest,
} from './types'

/** Error with a message ready to show to the user (in Portuguese, as the backend sends it). */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

const OFFLINE_MESSAGE = 'Não foi possível falar com o servidor. Confira se o backend está rodando (uvicorn).'

/** Turns FastAPI's `detail` (a string or a list of validation errors) into one readable message. */
export function detailMessage(detail: unknown): string | null {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (item && typeof item === 'object' && 'msg' in item ? String(item.msg) : null))
      .filter((msg): msg is string => Boolean(msg))
      .map((msg) => msg.replace(/^Value error, /, ''))
    return messages.length ? messages.join(' ') : null
  }
  return null
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return 'Erro inesperado.'
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const isJson = typeof init.body === 'string'
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      ...init,
      headers: isJson ? { 'Content-Type': 'application/json', ...init.headers } : init.headers,
    })
  } catch {
    throw new ApiError(0, OFFLINE_MESSAGE)
  }

  if (!response.ok) {
    let message: string | null = null
    try {
      message = detailMessage((await response.json())?.detail)
    } catch {
      // not JSON: usually the dev proxy answering because the backend is down
    }
    if (!message) message = response.status >= 500 ? OFFLINE_MESSAGE : `Erro ${response.status}.`
    throw new ApiError(response.status, message)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

/** Same as `request`, but a 404 becomes `null` (e.g. "no profile yet"). */
async function requestOrNull<T>(path: string): Promise<T | null> {
  try {
    return await request<T>(path)
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null
    throw error
  }
}

const json = (body: unknown) => JSON.stringify(body)

export const api = {
  // profile
  getProfile: () => requestOrNull<ProfileOut>('/profile'),
  uploadProfile: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<ProfileDraft>('/profile/upload', { method: 'POST', body: form })
  },
  saveProfile: (data: ProfileData, rawText: string) =>
    request<ProfileOut>('/profile', { method: 'PUT', body: json({ data, raw_text: rawText }) }),

  // jobs
  listJobs: () => request<JobSummary[]>('/jobs'),
  getJob: (id: number) => request<JobOut>(`/jobs/${id}`),
  createJob: (text: string, url: string | null) => request<JobOut>('/jobs', { method: 'POST', body: json({ text, url }) }),
  deleteJob: (id: number) => request<void>(`/jobs/${id}`, { method: 'DELETE' }),
  chooseTrack: (id: number, track: number) =>
    request<JobOut>(`/jobs/${id}/track`, { method: 'PUT', body: json({ track }) }),
  updateApplication: (id: number, changes: { status?: ApplicationStatus; notes?: string }) =>
    request<JobOut>(`/jobs/${id}/application`, { method: 'PATCH', body: json(changes) }),

  // analysis
  getAnalysis: (jobId: number) => requestOrNull<AnalysisOut>(`/jobs/${jobId}/analysis`),
  analyze: (jobId: number) => request<AnalysisOut>(`/jobs/${jobId}/analysis`, { method: 'POST' }),

  // texts
  listTexts: (jobId: number) => request<TextOut[]>(`/jobs/${jobId}/texts`),
  generateText: (jobId: number, body: TextRequest) =>
    request<TextOut>(`/jobs/${jobId}/texts`, { method: 'POST', body: json(body) }),

  // dashboard
  getInsights: () => request<Insights>('/insights'),
}
