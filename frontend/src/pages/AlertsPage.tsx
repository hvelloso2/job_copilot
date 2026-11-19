import { ExternalLink, Mail, RotateCcw, X } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'

import { ErrorAlert, Loading } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { checkSummary, plural } from '@/lib/alerts'
import { api, errorMessage } from '@/lib/api'
import { formatDate, formatDateTime } from '@/lib/format'
import type { AlertsStatus, Lead, LeadStatus } from '@/lib/types'

const TABS: { status: LeadStatus; label: string }[] = [
  { status: 'new', label: 'Novas' },
  { status: 'imported', label: 'Importadas' },
  { status: 'dismissed', label: 'Descartadas' },
]

function SetupCard() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Configure o e-mail</CardTitle>
        <CardDescription>A leitura é só de leitura: nada é marcado como lido, movido ou apagado.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <ol className="list-decimal space-y-1 pl-5">
          <li>Crie alertas de vaga nos sites que você usa (LinkedIn, Gupy, Indeed…) com as buscas que te interessam.</li>
          <li>
            No Gmail, ative a verificação em duas etapas e crie uma <strong>senha de app</strong> (Conta Google › Segurança ›
            Senhas de app). Não use a senha da conta.
          </li>
          <li>
            No arquivo <code>backend/.env</code>, preencha <code>IMAP_USER</code> (seu e-mail) e <code>IMAP_PASSWORD</code> (a
            senha de app). Outros provedores: ajuste <code>IMAP_HOST</code>.
          </li>
          <li>Reinicie o backend e volte a esta página.</li>
        </ol>
      </CardContent>
    </Card>
  )
}

function LeadRow({ lead, onStatus }: { lead: Lead; onStatus: (lead: Lead, status: 'new' | 'dismissed') => void }) {
  const details = [lead.company, lead.location, lead.source, lead.received_at && formatDate(lead.received_at)].filter(Boolean)
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 border-t py-2 first:border-t-0">
      <div className="min-w-0">
        <a href={lead.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-medium hover:underline">
          {lead.title}
          <ExternalLink className="size-3" />
        </a>
        <p className="text-xs text-muted-foreground">{details.join(' · ')}</p>
      </div>
      <div className="flex gap-1">
        {lead.status === 'imported' && lead.job_id !== null && (
          <Button variant="outline" size="sm" asChild>
            <Link to={`/vagas/${lead.job_id}`}>Ver no quadro</Link>
          </Button>
        )}
        {lead.status === 'new' && (
          <Button variant="ghost" size="sm" aria-label={`Descartar ${lead.title}`} onClick={() => onStatus(lead, 'dismissed')}>
            <X />
            Descartar
          </Button>
        )}
        {lead.status === 'dismissed' && (
          <Button variant="ghost" size="sm" aria-label={`Restaurar ${lead.title}`} onClick={() => onStatus(lead, 'new')}>
            <RotateCcw />
            Restaurar
          </Button>
        )}
      </div>
    </li>
  )
}

/** Postings announced by job alert emails. The user opens the link and sends the page with the extension. */
export default function AlertsPage() {
  const [status, setStatus] = useState<AlertsStatus | null>(null)
  const [leads, setLeads] = useState<Lead[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [checking, setChecking] = useState(false)
  const [tab, setTab] = useState<LeadStatus>('new')

  const load = useCallback(
    () =>
      Promise.all([api.getAlerts(), api.listLeads()])
        .then(([alerts, list]) => {
          setStatus(alerts)
          setLeads(list)
          setLoadError(null)
        })
        .catch((e) => setLoadError(errorMessage(e))),
    [],
  )

  useEffect(() => {
    load()
  }, [load])

  if (loadError) return <ErrorAlert title="Não foi possível carregar os alertas" message={loadError} />
  if (!status) return <Loading message="Carregando os alertas…" />

  const check = async () => {
    setChecking(true)
    try {
      const result = await api.checkAlerts()
      toast.success(checkSummary(result))
      if (result.errors.length) toast.error(`Não foi possível ler: ${result.errors.join('; ')}`)
      await load()
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setChecking(false)
    }
  }

  const changeStatus = async (lead: Lead, next: 'new' | 'dismissed') => {
    try {
      const updated = await api.updateLead(lead.id, next)
      setLeads((current) => current.map((l) => (l.id === updated.id ? updated : l)))
    } catch (e) {
      toast.error(errorMessage(e))
    }
  }

  const shown = leads.filter((l) => l.status === tab)
  const count = (s: LeadStatus) => leads.filter((l) => l.status === s).length

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Alertas de vagas</h1>
          <p className="text-sm text-muted-foreground">
            Vagas dos e-mails de alerta que os sites te mandam. Abra a vaga e clique no botão da extensão{' '}
            <strong>job-copilot</strong> no navegador: ela vai para o quadro com o texto completo.
          </p>
        </div>
        <Button onClick={check} disabled={!status.configured || checking}>
          <Mail />
          {checking ? 'Lendo e-mails…' : 'Ler e-mails de alerta'}
        </Button>
      </div>

      {checking && <Loading message="Lendo os e-mails novos (a IA lista as vagas de cada um)…" />}

      {status.configured ? (
        <p className="text-xs text-muted-foreground">
          {status.mailbox} · remetentes: {status.senders.join(', ')} · últimos {status.days} dias ·{' '}
          {plural(status.emails_read, 'e-mail lido', 'e-mails lidos')} até agora
          {status.last_read_at && ` · última leitura ${formatDateTime(status.last_read_at)}`}
        </p>
      ) : (
        <SetupCard />
      )}

      <div className="flex gap-1" role="tablist">
        {TABS.map((t) => (
          <Button
            key={t.status}
            role="tab"
            aria-selected={tab === t.status}
            variant={tab === t.status ? 'secondary' : 'ghost'}
            size="sm"
            onClick={() => setTab(t.status)}
          >
            {t.label} ({count(t.status)})
          </Button>
        ))}
      </div>

      {shown.length === 0 ? (
        <p className="rounded-xl border border-dashed bg-background p-6 text-center text-sm text-muted-foreground">
          {tab === 'new' ? 'Nenhuma vaga nova. Clique em Ler e-mails de alerta.' : 'Nada aqui.'}
        </p>
      ) : (
        <Card>
          <CardContent>
            <ul>
              {shown.map((lead) => (
                <LeadRow key={lead.id} lead={lead} onStatus={changeStatus} />
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
