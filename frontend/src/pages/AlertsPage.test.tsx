import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { toast } from 'sonner'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { checkSummary } from '@/lib/alerts'
import { api } from '@/lib/api'
import type { AlertsStatus, Lead } from '@/lib/types'

import AlertsPage from './AlertsPage'

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }))

const STATUS: AlertsStatus = {
  configured: true, mailbox: 'eu@gmail.com / INBOX', senders: ['linkedin.com'], days: 14, emails_read: 3, last_read_at: null,
}

function lead(id: number, title: string, status: Lead['status'], job_id: number | null = null): Lead {
  return { id, url: `https://www.linkedin.com/jobs/view/${id}/`, title, company: 'Acme', location: 'Remoto',
           source: 'linkedin.com', status, received_at: '2026-11-18T10:00:00Z', job_id }
}

const renderPage = () => render(<MemoryRouter><AlertsPage /></MemoryRouter>)

afterEach(() => vi.restoreAllMocks())

describe('checkSummary', () => {
  it('summarizes a check', () => {
    expect(checkSummary({ emails_read: 0, leads_new: 0, leads_known: 0, errors: [] })).toBe('Nenhum e-mail de alerta novo.')
    expect(checkSummary({ emails_read: 2, leads_new: 1, leads_known: 3, errors: [] })).toBe(
      '2 e-mails lidos, 1 vaga nova, 3 repetidas de e-mails anteriores.',
    )
  })
})

describe('AlertsPage', () => {
  it('lists new leads, dismisses one and shows imported ones with a link to the board', async () => {
    vi.spyOn(api, 'getAlerts').mockResolvedValue(STATUS)
    vi.spyOn(api, 'listLeads').mockResolvedValue([lead(1, 'Dev Python Júnior', 'new'), lead(2, 'Backend Jr', 'imported', 7)])
    const update = vi.spyOn(api, 'updateLead').mockImplementation(async (id, status) => ({ ...lead(id, 'Dev Python Júnior', status) }))
    renderPage()

    const link = await screen.findByRole('link', { name: /Dev Python Júnior/ })
    expect(link).toHaveAttribute('href', 'https://www.linkedin.com/jobs/view/1/')
    expect(screen.getByText(/Acme · Remoto · linkedin.com/)).toBeInTheDocument()
    expect(screen.queryByText('Backend Jr')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Descartar Dev Python Júnior' }))
    expect(update).toHaveBeenCalledWith(1, 'dismissed')
    expect(await screen.findByText(/Nenhuma vaga nova/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('tab', { name: 'Importadas (1)' }))
    expect(screen.getByRole('link', { name: 'Ver no quadro' })).toHaveAttribute('href', '/vagas/7')
  })

  it('reads the emails and reloads the list', async () => {
    vi.spyOn(api, 'getAlerts').mockResolvedValue(STATUS)
    const list = vi.spyOn(api, 'listLeads').mockResolvedValueOnce([]).mockResolvedValue([lead(1, 'Dev Python Júnior', 'new')])
    vi.spyOn(api, 'checkAlerts').mockResolvedValue({ emails_read: 1, leads_new: 1, leads_known: 0, errors: [] })
    renderPage()

    await userEvent.click(await screen.findByRole('button', { name: 'Ler e-mails de alerta' }))

    expect(toast.success).toHaveBeenCalledWith('1 e-mail lido, 1 vaga nova.')
    expect(await screen.findByRole('link', { name: /Dev Python Júnior/ })).toBeInTheDocument()
    expect(list).toHaveBeenCalledTimes(2)
  })

  it('explains the setup when the mailbox is not configured', async () => {
    vi.spyOn(api, 'getAlerts').mockResolvedValue({ ...STATUS, configured: false, mailbox: '' })
    vi.spyOn(api, 'listLeads').mockResolvedValue([])
    renderPage()

    expect(await screen.findByText('Configure o e-mail')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ler e-mails de alerta' })).toBeDisabled()
  })
})
