import { CheckCircle2, Copy, ShieldAlert, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { ErrorAlert, Loading } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { api, errorMessage } from '@/lib/api'
import { formatDateTime, TEXT_FORMAT_LABEL, TEXT_TYPE_LABEL } from '@/lib/format'
import type { TextFormat, TextOut, TextType } from '@/lib/types'

import { HighlightedText } from './HighlightedText'

function TextResult({ item }: { item: TextOut }) {
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(item.text)
      toast.success(
        item.unsupported_claims || item.placeholders.length
          ? 'Copiado. Lembre de corrigir o que está marcado antes de enviar.'
          : 'Copiado.',
      )
    } catch {
      toast.error('Não foi possível copiar. Selecione o texto e copie manualmente.')
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {item.unsupported_claims > 0 ? (
          <span className="inline-flex items-center gap-1.5 text-sm font-medium text-red-700">
            <ShieldAlert className="size-4" />
            {item.unsupported_claims} afirmação(ões) sem suporte no seu perfil (em vermelho)
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 text-sm text-emerald-700">
            <CheckCircle2 className="size-4" />
            Todas as afirmações conferem com o seu perfil
          </span>
        )}
        <Button size="sm" variant="outline" className="ml-auto" onClick={copy}>
          <Copy />
          Copiar texto
        </Button>
      </div>

      <div className="rounded-lg border bg-background p-4">
        <HighlightedText value={item.highlighted_text} claims={item.claims} />
      </div>

      {item.placeholders.length > 0 && (
        <div className="text-sm">
          <p className="font-medium text-amber-800">Para preencher (em amarelo):</p>
          <ul className="list-disc pl-5 text-muted-foreground">
            {item.placeholders.map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
        </div>
      )}
      {item.warnings.length > 0 && (
        <p className="text-sm text-amber-800">
          Também aparecem no texto e não estão no seu perfil: <strong>{item.warnings.join(', ')}</strong>. Confira se o
          texto não afirma que você tem isso.
        </p>
      )}
      {item.claims.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer text-muted-foreground">
            Afirmações verificadas ({item.claims.length})
          </summary>
          <ul className="mt-2 space-y-1.5">
            {item.claims.map((c, i) => (
              <li key={i} className="flex items-start gap-2">
                {c.supported ? (
                  <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600" />
                ) : (
                  <ShieldAlert className="mt-0.5 size-4 shrink-0 text-red-600" />
                )}
                <span>
                  “{c.claim}”
                  <span className="block text-xs text-muted-foreground">
                    {c.supported ? `Perfil: “${c.evidence}”` : c.reason}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}

export function TextsPanel({
  jobId,
  texts,
  disabledReason,
  onGenerated,
}: {
  jobId: number
  texts: TextOut[]
  disabledReason: string | null
  onGenerated: (text: TextOut) => void
}) {
  const [type, setType] = useState<TextType>('answer')
  const [format, setFormat] = useState<TextFormat>('written')
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [latestId, setLatestId] = useState<number | null>(null)

  const latest = texts.find((t) => t.id === latestId) ?? null
  const history = texts.filter((t) => t.id !== latestId)
  const missingQuestion = type === 'answer' && !question.trim()

  const generate = async () => {
    setBusy(true)
    setError(null)
    try {
      const created = await api.generateText(
        jobId,
        type === 'answer' ? { type, question: question.trim(), format } : { type },
      )
      onGenerated(created)
      setLatestId(created.id)
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Gerar texto</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-4">
            <div className="space-y-1.5">
              <Label>Tipo</Label>
              <Select value={type} onValueChange={(v) => setType(v as TextType)} disabled={busy}>
                <SelectTrigger className="w-64">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(Object.keys(TEXT_TYPE_LABEL) as TextType[]).map((t) => (
                    <SelectItem key={t} value={t}>
                      {TEXT_TYPE_LABEL[t]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {type === 'answer' && (
              <div className="space-y-1.5">
                <Label>Formato</Label>
                <Select value={format} onValueChange={(v) => setFormat(v as TextFormat)} disabled={busy}>
                  <SelectTrigger className="w-52">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(Object.keys(TEXT_FORMAT_LABEL) as TextFormat[]).map((f) => (
                      <SelectItem key={f} value={f}>
                        {TEXT_FORMAT_LABEL[f]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
          {type === 'answer' && (
            <div className="space-y-1.5">
              <Label htmlFor="question">Pergunta do processo seletivo</Label>
              <Textarea
                id="question"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                rows={3}
                placeholder="Ex.: Conte sobre um projeto em que você integrou IA em uma aplicação."
                disabled={busy}
              />
            </div>
          )}
          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={generate} disabled={busy || missingQuestion || Boolean(disabledReason)}>
              <Sparkles />
              Gerar
            </Button>
            {disabledReason && <span className="text-sm text-muted-foreground">{disabledReason}</span>}
          </div>
          {busy && <Loading message="Gerando o texto e conferindo cada afirmação com o seu perfil… (pode levar até 1 minuto)" />}
          {error && <ErrorAlert message={error} />}
        </CardContent>
      </Card>

      {latest && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              {TEXT_TYPE_LABEL[latest.type]}
              {latest.type === 'answer' && ` · ${TEXT_FORMAT_LABEL[latest.format]}`}
            </CardTitle>
            {latest.question && <p className="text-sm text-muted-foreground">“{latest.question}”</p>}
          </CardHeader>
          <CardContent>
            <TextResult item={latest} />
          </CardContent>
        </Card>
      )}

      {history.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold">Histórico</h3>
          {history.map((item) => (
            <details key={item.id} className="rounded-lg border bg-background p-3">
              <summary className="cursor-pointer text-sm">
                <span className="font-medium">{TEXT_TYPE_LABEL[item.type]}</span>
                {item.type === 'answer' && ` · ${TEXT_FORMAT_LABEL[item.format]}`}
                <span className="text-muted-foreground"> · {formatDateTime(item.created_at)}</span>
                {item.unsupported_claims > 0 && (
                  <span className="text-red-700"> · {item.unsupported_claims} sem suporte</span>
                )}
                {item.question && <span className="block text-xs text-muted-foreground">“{item.question}”</span>}
              </summary>
              <div className="mt-3">
                <TextResult item={item} />
              </div>
            </details>
          ))}
        </div>
      )}
    </div>
  )
}
