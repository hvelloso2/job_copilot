import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api, ApiError } from '@/lib/api'
import type { JobOut, JobSummary } from '@/lib/types'

import { useJobsStore } from './jobsStore'

const job = (id: number, overrides: Partial<JobSummary> = {}): JobSummary => ({
  id,
  company: 'Acme',
  title: `Vaga ${id}`,
  status: 'saved',
  needs_track_choice: false,
  score: null,
  created_at: '2026-11-01T10:00:00',
  updated_at: '2026-11-01T10:00:00',
  ...overrides,
})

describe('jobsStore.moveJob', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    useJobsStore.setState({ jobs: [job(1), job(2)], loading: false, error: null })
  })

  it('moves the card at once and keeps the server version', async () => {
    let resolve!: (value: JobOut) => void
    vi.spyOn(api, 'updateApplication').mockReturnValue(new Promise((r) => (resolve = r)))

    const pending = useJobsStore.getState().moveJob(1, 'applied')
    expect(useJobsStore.getState().jobs[0].status).toBe('applied') // optimistic

    resolve({ ...job(1, { status: 'applied', updated_at: '2026-11-17T12:00:00' }), url: null, raw_text: '', tracks: [], selected_track: 0, status_history: [], notes: '' })
    await pending

    expect(api.updateApplication).toHaveBeenCalledWith(1, { status: 'applied' })
    expect(useJobsStore.getState().jobs[0]).toEqual(job(1, { status: 'applied', updated_at: '2026-11-17T12:00:00' }))
  })

  it('rolls back when the API fails', async () => {
    vi.spyOn(api, 'updateApplication').mockRejectedValue(new ApiError(500, 'falhou'))

    await expect(useJobsStore.getState().moveJob(1, 'interview')).rejects.toThrow('falhou')

    expect(useJobsStore.getState().jobs[0].status).toBe('saved')
  })

  it('ignores a drop on the same column', async () => {
    const spy = vi.spyOn(api, 'updateApplication')
    await useJobsStore.getState().moveJob(2, 'saved')
    expect(spy).not.toHaveBeenCalled()
  })
})

describe('jobsStore.upsertJob/removeJob', () => {
  beforeEach(() => useJobsStore.setState({ jobs: [job(1)], loading: false, error: null }))

  it('adds new jobs first and replaces existing ones', () => {
    useJobsStore.getState().upsertJob(job(2))
    useJobsStore.getState().upsertJob(job(1, { score: 76 }))
    expect(useJobsStore.getState().jobs.map((j) => [j.id, j.score])).toEqual([
      [2, null],
      [1, 76],
    ])
    useJobsStore.getState().removeJob(2)
    expect(useJobsStore.getState().jobs.map((j) => j.id)).toEqual([1])
  })
})
