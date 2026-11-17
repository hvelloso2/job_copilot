import { AlertTriangle, CheckCircle2, RefreshCw, ShieldAlert, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { ColorBadge, ErrorAlert, Loading, Section } from '@/components/common'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { api, errorMessage } from '@/lib/api'
import { formatDateTime, REQUIREMENT_CLASS, REQUIREMENT_LABEL, scoreClass } from '@/lib/format'
import type { AnalysisOut, RequirementResult } from '@/lib/types'
import { cn } from '@/lib/utils'

function RequirementRow({ req }: { req: RequirementResult }) {
  return (
    <li className="space-y-1 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <ColorBadge className={REQUIREMENT_CLASS[req.status]}>{REQUIREMENT_LABEL[req.status]}</ColorBadge>
        <span className="text-xs text-muted-foreground">{req.kind === 'required' ? 'obrigatório' : 'desejável'}</span>
        <span className="text-sm font-medium">{req.requirement}</span>
      </div>
      {req.explanation && <p className="text-sm text-muted-foreground">{req.explanation}</p>}
      {req.evidence && (
        <p
          className={cn(
            'flex items-start gap-1.5 text-xs',
            req.evidence_verified ? 'text-emerald-700' : 'text-red-700 line-through decoration-red-400',
          )}
        >
          {req.evidence_verified && <CheckCircle2 className="mt-px size-3.5 shrink-0" />}
          <span>Evidência: “{req.evidence}”</span>
        </p>
      )}
      {req.note && (
        <p className="flex items-start gap-1.5 text-xs font-medium text-red-700">
          <ShieldAlert className="mt-px size-3.5 shrink-0" />
          {req.note}
          {req.model_status && req.model_status !== req.status && ` (o modelo disse: ${REQUIREMENT_LABEL[req.model_status]})`}
        </p>
      )}
    </li>
  )
}

function AnalysisView({ analysis }: { analysis: AnalysisOut }) {
  const { verification: v } = analysis
  const met = analysis.requirements.filter((r) => r.status === 'meets').length
  const rejected = v.evidence_rejected + v.strengths_rejected

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-4">
        <div className={cn('flex size-20 flex-col items-center justify-center rounded-2xl border', scoreClass(analysis.score))}>
          <span className="text-3xl font-bold">{analysis.score ?? '—'}</span>
          <span className="text-[10px] uppercase tracking-wide">nota</span>
        </div>
        <div className="space-y-1 text-sm">
          <p>
            Atende <strong>{met}</strong> de <strong>{analysis.requirements.length}</strong> requisitos
            {' '}(trilha: {analysis.track_title})
          </p>
          <p className="text-muted-foreground">
            Nota calculada em código: obrigatórios pesam 2, desejáveis 1. Perfil versão {analysis.profile_version},{' '}
            {formatDateTime(analysis.created_at)}.
          </p>
          {rejected > 0 ? (
            <p className="flex items-center gap-1.5 font-medium text-red-700">
              <ShieldAlert className="size-4" />
              O verificador rejeitou {rejected} evidência(s) que não existem no seu perfil.
            </p>
          ) : (
            <p className="flex items-center gap-1.5 text-emerald-700">
              <CheckCircle2 className="size-4" />
              Todas as evidências citadas existem no seu perfil.
            </p>
          )}
        </div>
      </div>

      <Section title="Requisitos">
        <ul className="divide-y">
          {analysis.requirements.map((req, i) => (
            <RequirementRow key={i} req={req} />
          ))}
        </ul>
      </Section>

      <div className="grid gap-6 md:grid-cols-2">
        <Section title="Pontos fortes para destacar">
          <ul className="space-y-2">
            {analysis.strengths.map((s, i) => (
              <li key={i} className="text-sm">
                <p className={cn(!s.evidence_verified && 'text-red-700 line-through')}>{s.point}</p>
                <p className="text-xs text-muted-foreground">
                  {s.evidence_verified ? `“${s.evidence}”` : 'Evidência não encontrada no perfil.'}
                </p>
              </li>
            ))}
            {analysis.strengths.length === 0 && <li className="text-sm text-muted-foreground">Nenhum.</li>}
          </ul>
        </Section>
        <Section title="Lacunas">
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {analysis.gaps.map((g, i) => (
              <li key={i}>{g}</li>
            ))}
            {analysis.gaps.length === 0 && <li className="list-none text-muted-foreground">Nenhuma.</li>}
          </ul>
        </Section>
      </div>

      <Section
        title="Sugestões de ajuste no currículo"
        description="Só reescrevem o que já está no seu perfil. Sugestões marcadas em vermelho trazem algo que você não tem: não use sem corrigir."
      >
        <div className="space-y-3">
          {analysis.resume_suggestions.map((s, i) => {
            const flagged = s.unsupported.length > 0 || !s.original_found
            return (
              <Card key={i} className={cn('py-3', flagged && 'border-red-300')}>
                <CardContent className="space-y-1.5 px-4 text-sm">
                  <p className="text-muted-foreground line-through decoration-muted-foreground/50">{s.original}</p>
                  <p className="font-medium">{s.suggested}</p>
                  <p className="text-xs text-muted-foreground">{s.reason}</p>
                  {s.unsupported.length > 0 && (
                    <p className="flex items-center gap-1.5 text-xs font-medium text-red-700">
                      <AlertTriangle className="size-3.5" />
                      Não está no seu perfil: {s.unsupported.join(', ')}
                    </p>
                  )}
                  {!s.original_found && (
                    <p className="flex items-center gap-1.5 text-xs font-medium text-amber-700">
                      <AlertTriangle className="size-3.5" />
                      O trecho original não foi encontrado no perfil.
                    </p>
                  )}
                </CardContent>
              </Card>
            )
          })}
          {analysis.resume_suggestions.length === 0 && <p className="text-sm text-muted-foreground">Nenhuma.</p>}
        </div>
      </Section>

      <Section title="O que estudar">
        <ol className="list-decimal space-y-1 pl-5 text-sm">
          {analysis.study_plan.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ol>
      </Section>
    </div>
  )
}

export function AnalysisPanel({
  jobId,
  analysis,
  disabledReason,
  onAnalyzed,
}: {
  jobId: number
  analysis: AnalysisOut | null
  disabledReason: string | null
  onAnalyzed: (analysis: AnalysisOut) => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = async () => {
    setBusy(true)
    setError(null)
    try {
      onAnalyzed(await api.analyze(jobId))
      toast.success('Análise concluída.')
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const button = (
    <Button onClick={run} disabled={busy || Boolean(disabledReason)} variant={analysis ? 'outline' : 'default'}>
      {analysis ? <RefreshCw /> : <Sparkles />}
      {analysis ? 'Analisar de novo' : 'Analisar compatibilidade'}
    </Button>
  )

  return (
    <div className="space-y-4">
      {analysis?.outdated && (
        <Alert>
          <AlertTriangle />
          <AlertTitle>Seu perfil mudou depois desta análise</AlertTitle>
          <AlertDescription>Analise de novo para usar a versão atual do perfil.</AlertDescription>
        </Alert>
      )}
      <div className="flex flex-wrap items-center gap-3">
        {button}
        {disabledReason && <span className="text-sm text-muted-foreground">{disabledReason}</span>}
      </div>
      {busy && <Loading message="Comparando seu perfil com a vaga e verificando as evidências… (pode levar até 1 minuto)" />}
      {error && <ErrorAlert message={error} />}
      {analysis ? (
        <AnalysisView analysis={analysis} />
      ) : (
        !busy && (
          <p className="text-sm text-muted-foreground">
            Esta vaga ainda não foi analisada. A análise compara cada requisito com o seu perfil salvo.
          </p>
        )
      )}
    </div>
  )
}
