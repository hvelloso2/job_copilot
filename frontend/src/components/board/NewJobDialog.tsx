import { Plus } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'

import { ErrorAlert, Loading } from '@/components/common'
import { JobDataView } from '@/components/job/JobDataView'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { api, errorMessage } from '@/lib/api'
import type { JobOut } from '@/lib/types'
import { cn } from '@/lib/utils'
import { useJobsStore } from '@/stores/jobsStore'

/**
 * "Nova vaga": paste the posting, Claude extracts it, the user checks the result and
 * confirms (keeps it) or discards it (deletes it).
 */
export function NewJobDialog() {
  const navigate = useNavigate()
  const { upsertJob, removeJob } = useJobsStore()
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [url, setUrl] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [job, setJob] = useState<JobOut | null>(null)
  const [track, setTrack] = useState(0)

  const reset = () => {
    setText('')
    setUrl('')
    setError(null)
    setJob(null)
    setTrack(0)
  }

  const extract = async () => {
    setBusy('Extraindo os dados da vaga com o Claude…')
    setError(null)
    try {
      const created = await api.createJob(text, url.trim() || null)
      setJob(created)
      setTrack(created.selected_track ?? 0)
      upsertJob(created)
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(null)
    }
  }

  const confirm = async () => {
    if (!job) return
    setBusy('Salvando…')
    setError(null)
    try {
      const saved = job.tracks.length > 1 ? await api.chooseTrack(job.id, track) : job
      upsertJob(saved)
      toast.success('Vaga salva em "Salva".')
      setOpen(false)
      reset()
      navigate(`/vagas/${saved.id}`)
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(null)
    }
  }

  const discard = async () => {
    if (!job) return
    setBusy('Descartando…')
    try {
      await api.deleteJob(job.id)
      removeJob(job.id)
      setJob(null)
      toast('Vaga descartada.')
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(null)
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (busy) return // don't close in the middle of a request
        // closing after extraction keeps the job: it is already saved
        if (!next) reset()
        setOpen(next)
      }}
    >
      <DialogTrigger asChild>
        <Button>
          <Plus />
          Nova vaga
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{job ? 'Confira os dados extraídos' : 'Nova vaga'}</DialogTitle>
          <DialogDescription>
            {job
              ? 'Veja se os requisitos saíram separados e corretos. Se algo estiver errado, descarte e tente de novo.'
              : 'Cole o texto completo da vaga, do jeito que está no site.'}
          </DialogDescription>
        </DialogHeader>

        {!job && (
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="job-text">Texto da vaga</Label>
              <Textarea
                id="job-text"
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={12}
                placeholder="Cole aqui a descrição da vaga…"
                disabled={Boolean(busy)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="job-url">Link (opcional)</Label>
              <Input
                id="job-url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://…"
                disabled={Boolean(busy)}
              />
            </div>
          </div>
        )}

        {job && (
          <div className="space-y-4">
            {job.tracks.length > 1 && (
              <div className="space-y-2">
                <p className="text-sm font-medium">
                  Esta vaga tem {job.tracks.length} trilhas. Escolha qual você quer acompanhar:
                </p>
                <div className="flex flex-wrap gap-2">
                  {job.tracks.map((t, i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={() => setTrack(i)}
                      className={cn(
                        'rounded-md border px-3 py-1.5 text-sm transition-colors',
                        i === track ? 'border-primary bg-primary text-primary-foreground' : 'hover:bg-muted',
                      )}
                    >
                      {t.title}
                    </button>
                  ))}
                </div>
              </div>
            )}
            <JobDataView data={job.tracks[track]} />
          </div>
        )}

        {error && <ErrorAlert message={error} />}
        {busy && <Loading message={busy} />}

        <DialogFooter>
          {!job ? (
            <Button onClick={extract} disabled={!text.trim() || Boolean(busy)}>
              Extrair dados
            </Button>
          ) : (
            <>
              <Button variant="outline" onClick={discard} disabled={Boolean(busy)}>
                Descartar
              </Button>
              <Button onClick={confirm} disabled={Boolean(busy)}>
                Confirmar
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
