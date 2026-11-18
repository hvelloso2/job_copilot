import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/lib/api'
import type { Insights } from '@/lib/types'

import { funnelItems, scoreItems } from '@/components/insights/items'

import InsightsPage from './InsightsPage'

const INSIGHTS: Insights = {
  total_jobs: 4,
  has_profile: true,
  skills: [
    { name: 'PostgreSQL', count: 3, share: 75, in_profile: true },
    { name: 'Kubernetes', count: 2, share: 50, in_profile: false },
  ],
  top_gaps: [{ name: 'Kubernetes', count: 2, share: 50, in_profile: false }],
  funnel: [
    { status: 'saved', current: 1, reached: 4, rate_from_previous: null },
    { status: 'applied', current: 1, reached: 3, rate_from_previous: 75 },
    { status: 'test', current: 0, reached: 2, rate_from_previous: 67 },
    { status: 'interview', current: 1, reached: 1, rate_from_previous: 50 },
    { status: 'offer', current: 0, reached: 0, rate_from_previous: 0 },
    { status: 'closed', current: 1, reached: 1, rate_from_previous: null },
  ],
  scores_by_status: [
    { status: 'saved', average: null, analyzed: 0, total: 1 },
    { status: 'applied', average: 70, analyzed: 2, total: 3 },
    { status: 'test', average: null, analyzed: 0, total: 0 },
    { status: 'interview', average: null, analyzed: 0, total: 0 },
    { status: 'offer', average: null, analyzed: 0, total: 0 },
    { status: 'closed', average: null, analyzed: 0, total: 0 },
  ],
}

afterEach(() => vi.restoreAllMocks())

describe('InsightsPage', () => {
  it('shows gaps, skills, funnel and scores', async () => {
    vi.spyOn(api, 'getInsights').mockResolvedValue(INSIGHTS)
    render(<MemoryRouter><InsightsPage /></MemoryRouter>)

    const gaps = await screen.findByRole('list', { name: 'Lacunas mais frequentes' })
    expect(gaps).toHaveTextContent('Kubernetes')
    expect(gaps).not.toHaveTextContent('PostgreSQL')
    expect(screen.getByRole('list', { name: 'Skills mais pedidas' })).toHaveTextContent('PostgreSQL3 vagas · 75%')
    expect(screen.getByText('1 candidatura encerrada', { exact: false })).toBeInTheDocument()
  })

  it('asks for a job when there is none', async () => {
    vi.spyOn(api, 'getInsights').mockResolvedValue({ ...INSIGHTS, total_jobs: 0, skills: [], top_gaps: [] })
    render(<MemoryRouter><InsightsPage /></MemoryRouter>)

    expect(await screen.findByText('Adicione uma vaga')).toBeInTheDocument()
  })
})

describe('chart items', () => {
  it('funnel leaves "closed" out and shows the advance rate', () => {
    const items = funnelItems(INSIGHTS.funnel)
    expect(items.map((i) => i.key)).toEqual(['saved', 'applied', 'test', 'interview', 'offer'])
    expect(items[1].valueLabel).toBe('3 · 75%')
    expect(items[0].valueLabel).toBe('4')
  })

  it('scores only list statuses that have jobs', () => {
    const items = scoreItems(INSIGHTS.scores_by_status)
    expect(items.map((i) => [i.key, i.valueLabel])).toEqual([
      ['saved', 'sem análise'],
      ['applied', '70 (2 de 3)'],
    ])
  })
})
