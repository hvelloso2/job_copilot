import { AlertTriangle, ArrowLeft, ExternalLink, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'

import { ColorBadge, ErrorAlert, Loading } from '@/components/common'
import { AnalysisPanel } from '@/components/job/AnalysisPanel'
import { JobDataView } from '@/components/job/JobDataView'
import { NotesPanel } from '@/components/job/NotesPanel'
import { TextsPanel } from '@/components/job/TextsPanel'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { api, errorMessage } from '@/lib/api'
import { formatDate, scoreClass, STATUS_LABEL, STATUS_ORDER } from '@/lib/format'
import type { AnalysisOut, ApplicationStatus, JobOut, TextOut } from '@/lib/types'
import { useJobsStore } from '@/stores/jobsStore'

interface PageData {
  job: JobOut
  analysis: AnalysisOut | null
  texts: TextOut[]
  hasProfile: boolean
}

export default function JobPage() {
  const id = Number(useParams().id)
  const navigate = useNavigate()
  const { upsertJob, removeJob } = useJobsStore()
  const [data, setData] = useState<PageData | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const [job, analysis, texts, profile] = await Promise.all([
        api.getJob(id),
        api.getAnalysis(id),
        api.listTexts(id),
        api.getProfile(),
      ])
      setData({ job, analysis, texts, hasProfile: profile !== null })
    } catch (e) {
      setError(errorMessage(e))
    }
  }, [id])

  useEffect(() => {
    void load()
  }, [load])

  if (error) {
    return (
      <div className="space-y-4">
        <BackLink />
        <ErrorAlert title="Não foi possível abrir a vaga" message={error} />
      </div>
    )
  }
  if (!data) return <Loading message="Carregando vaga…" />

  const { job, analysis, texts, hasProfile } = data
  const updateJob = (updated: JobOut) => {
    setData((d) => (d ? { ...d, job: updated } : d))
    upsertJob(updated)
  }

  const changeStatus = async (status: ApplicationStatus) => {
    try {
      updateJob(await api.updateApplication(job.id, { status }))
      toast.success(`Movida para "${STATUS_LABEL[status]}".`)
    } catch (e) {
      toast.error(errorMessage(e))
    }
  }

  const chooseTrack = async (track: number) => {
    try {
      updateJob(await api.chooseTrack(job.id, track))
    } catch (e) {
      toast.error(errorMessage(e))
    }
  }

  const deleteJob = async () => {
    if (!window.confirm('Apagar esta vaga, a análise e os textos gerados? Isso não pode ser desfeito.')) return
    try {
      await api.deleteJob(job.id)
      removeJob(job.id)
      toast('Vaga apagada.')
      navigate('/')
    } catch (e) {
      toast.error(errorMessage(e))
    }
  }

  const track = job.selected_track !== null ? job.tracks[job.selected_track] : null
  const analysisBlocked = !hasProfile
    ? 'Salve o seu perfil primeiro (página Perfil).'
    : job.needs_track_choice
      ? 'Escolha a trilha da vaga primeiro.'
      : null
  const textsBlocked = analysisBlocked ?? (analysis ? null : 'Analise a vaga primeiro (aba Análise).')

  return (
    <div className="space-y-6">
      <BackLink />

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <p className="text-sm text-muted-foreground">{job.company || 'Empresa não informada'}</p>
          <h1 className="text-2xl font-semibold">{job.title}</h1>
          <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
            <span>Cadastrada em {formatDate(job.created_at)}</span>
            {job.url && (
              <a href={job.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 hover:underline">
                <ExternalLink className="size-3.5" />
                Ver vaga original
              </a>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <ColorBadge className={scoreClass(analysis?.score ?? null)}>
            Nota {analysis?.score ?? '—'}
          </ColorBadge>
          <Select value={job.status} onValueChange={(v) => void changeStatus(v as ApplicationStatus)}>
            <SelectTrigger className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {STATUS_ORDER.map((s) => (
                <SelectItem key={s} value={s}>
                  {STATUS_LABEL[s]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="ghost" size="icon" onClick={deleteJob} aria-label="Apagar vaga">
            <Trash2 />
          </Button>
        </div>
      </div>

      {job.tracks.length > 1 && (
        <Alert>
          <AlertTriangle />
          <AlertTitle>
            {job.needs_track_choice ? 'Escolha qual trilha você quer acompanhar' : 'Esta vaga tem mais de uma trilha'}
          </AlertTitle>
          <AlertDescription>
            <div className="mt-2 flex flex-wrap gap-2">
              {job.tracks.map((t, i) => (
                <Button
                  key={i}
                  size="sm"
                  variant={job.selected_track === i ? 'default' : 'outline'}
                  onClick={() => void chooseTrack(i)}
                >
                  {t.title}
                </Button>
              ))}
            </div>
          </AlertDescription>
        </Alert>
      )}

      <Tabs defaultValue="analysis">
        <TabsList>
          <TabsTrigger value="analysis">Análise</TabsTrigger>
          <TabsTrigger value="texts">Textos{texts.length > 0 && ` (${texts.length})`}</TabsTrigger>
          <TabsTrigger value="job">Vaga</TabsTrigger>
          <TabsTrigger value="notes">Notas</TabsTrigger>
        </TabsList>
        <Card className="mt-3">
          <CardContent>
            <TabsContent value="analysis">
              <AnalysisPanel
                jobId={job.id}
                analysis={analysis}
                disabledReason={analysisBlocked}
                onAnalyzed={(a) => {
                  setData((d) => (d ? { ...d, analysis: a } : d))
                  upsertJob({ ...job, score: a.score })
                }}
              />
            </TabsContent>
            <TabsContent value="texts">
              <TextsPanel
                jobId={job.id}
                texts={texts}
                disabledReason={textsBlocked}
                onGenerated={(t) => setData((d) => (d ? { ...d, texts: [t, ...d.texts] } : d))}
              />
            </TabsContent>
            <TabsContent value="job" className="space-y-4">
              {track ? <JobDataView data={track} /> : <p className="text-sm text-muted-foreground">Escolha uma trilha.</p>}
              <details className="text-sm">
                <summary className="cursor-pointer text-muted-foreground">Texto original da vaga</summary>
                <p className="mt-2 whitespace-pre-wrap rounded-lg bg-muted p-3 text-xs">{job.raw_text}</p>
              </details>
            </TabsContent>
            <TabsContent value="notes">
              <NotesPanel key={job.id} job={job} onSaved={updateJob} />
            </TabsContent>
          </CardContent>
        </Card>
      </Tabs>
    </div>
  )
}

function BackLink() {
  return (
    <Link to="/" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
      <ArrowLeft className="size-4" />
      Candidaturas
    </Link>
  )
}
