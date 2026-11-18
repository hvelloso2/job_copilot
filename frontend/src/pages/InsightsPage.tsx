import { CheckCircle2, CircleAlert } from 'lucide-react'
import { type ReactNode, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { ErrorAlert, Loading } from '@/components/common'
import { BarList } from '@/components/insights/BarList'
import { funnelItems, scoreItems, skillItems, vagas } from '@/components/insights/items'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { api, errorMessage } from '@/lib/api'
import type { Insights } from '@/lib/types'

const MAX_SKILLS = 15

function Empty({ children }: { children: ReactNode }) {
  return <p className="text-sm text-muted-foreground">{children}</p>
}

export default function InsightsPage() {
  const [data, setData] = useState<Insights | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.getInsights().then(setData, (e) => setError(errorMessage(e)))
  }, [])

  if (error) return <ErrorAlert title="Não foi possível carregar o painel" message={error} />
  if (!data) return <Loading message="Calculando o painel…" />

  if (data.total_jobs === 0) {
    return (
      <div className="rounded-xl border border-dashed bg-background p-8 text-center text-sm text-muted-foreground">
        O painel aparece quando houver vagas salvas. <Link to="/" className="underline">Adicione uma vaga</Link> para começar.
      </div>
    )
  }

  const closed = data.funnel.find((step) => step.status === 'closed')
  const skills = data.skills.slice(0, MAX_SKILLS)

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Painel</h1>
        <p className="text-sm text-muted-foreground">Calculado a partir das {vagas(data.total_jobs)} salvas. Passe o mouse nas barras para ver detalhes.</p>
      </div>

      {!data.has_profile && (
        <ErrorAlert
          title="Sem perfil salvo"
          message="Todas as skills aparecem como lacunas até você salvar o perfil na página Perfil."
        />
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>O que estudar</CardTitle>
            <CardDescription>Skills mais pedidas que não estão no seu perfil.</CardDescription>
          </CardHeader>
          <CardContent>
            {data.top_gaps.length === 0 ? (
              <Empty>Seu perfil cobre todas as tecnologias pedidas nas vagas salvas.</Empty>
            ) : (
              <BarList ariaLabel="Lacunas mais frequentes" items={skillItems(data.top_gaps)} max={data.total_jobs} />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Skills mais pedidas</CardTitle>
            <CardDescription>
              Cada vaga conta uma vez. Nomes equivalentes (ex.: Postgres e PostgreSQL) são agrupados.
              {data.skills.length > MAX_SKILLS && ` Mostrando as ${MAX_SKILLS} primeiras de ${data.skills.length}.`}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {skills.length === 0 ? (
              <Empty>As vagas salvas não listam tecnologias.</Empty>
            ) : (
              <>
                <BarList ariaLabel="Skills mais pedidas" items={skillItems(skills)} max={data.total_jobs} />
                <div className="flex gap-4 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1.5"><CheckCircle2 className="size-3.5 text-emerald-600 dark:text-emerald-400" /> No perfil</span>
                  <span className="flex items-center gap-1.5"><CircleAlert className="size-3.5 text-red-600 dark:text-red-400" /> Falta no perfil</span>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Funil</CardTitle>
            <CardDescription>
              Quantas candidaturas chegaram a cada etapa (ou passaram dela) e a taxa de avanço da etapa anterior.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <BarList ariaLabel="Funil de candidaturas" items={funnelItems(data.funnel)} max={data.total_jobs} />
            {closed && closed.current > 0 && (
              <p className="text-xs text-muted-foreground">
                {closed.current === 1 ? '1 candidatura encerrada' : `${closed.current} candidaturas encerradas`} (contadas até a etapa em que pararam).
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Nota média por status</CardTitle>
            <CardDescription>Nota de compatibilidade (0 a 100) da análise mais recente de cada vaga.</CardDescription>
          </CardHeader>
          <CardContent>
            <BarList ariaLabel="Nota média por status" items={scoreItems(data.scores_by_status)} max={100} />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
