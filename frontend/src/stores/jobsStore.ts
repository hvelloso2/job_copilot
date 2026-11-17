import { create } from 'zustand'

import { api, errorMessage } from '@/lib/api'
import type { ApplicationStatus, JobOut, JobSummary } from '@/lib/types'

interface JobsState {
  jobs: JobSummary[]
  loading: boolean
  error: string | null
  fetchJobs: () => Promise<void>
  /** Moves a card to another column. Updates the board at once and rolls back if the API fails. */
  moveJob: (id: number, status: ApplicationStatus) => Promise<void>
  /** Puts the latest data of one job on the board (after creating or editing it). */
  upsertJob: (job: JobOut | JobSummary) => void
  removeJob: (id: number) => void
}

function toSummary(job: JobOut | JobSummary): JobSummary {
  const { id, company, title, status, needs_track_choice, score, created_at, updated_at } = job
  return { id, company, title, status, needs_track_choice, score, created_at, updated_at }
}

export const useJobsStore = create<JobsState>((set, get) => ({
  jobs: [],
  loading: false,
  error: null,

  fetchJobs: async () => {
    set({ loading: true, error: null })
    try {
      set({ jobs: await api.listJobs(), loading: false })
    } catch (error) {
      set({ error: errorMessage(error), loading: false })
    }
  },

  moveJob: async (id, status) => {
    const previous = get().jobs
    const current = previous.find((job) => job.id === id)
    if (!current || current.status === status) return
    set({
      jobs: previous.map((job) =>
        job.id === id ? { ...job, status, updated_at: new Date().toISOString() } : job,
      ),
    })
    try {
      get().upsertJob(await api.updateApplication(id, { status }))
    } catch (error) {
      set({ jobs: previous })
      throw error
    }
  },

  upsertJob: (job) => {
    const summary = toSummary(job)
    const jobs = get().jobs
    set({
      jobs: jobs.some((j) => j.id === job.id)
        ? jobs.map((j) => (j.id === job.id ? summary : j))
        : [summary, ...jobs],
    })
  },

  removeJob: (id) => set({ jobs: get().jobs.filter((job) => job.id !== id) }),
}))
