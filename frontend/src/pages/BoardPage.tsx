import { useEffect } from 'react'
import { toast } from 'sonner'

import { KanbanBoard } from '@/components/board/KanbanBoard'
import { NewJobDialog } from '@/components/board/NewJobDialog'
import { ErrorAlert, Loading } from '@/components/common'
import { errorMessage } from '@/lib/api'
import { STATUS_LABEL } from '@/lib/format'
import type { ApplicationStatus } from '@/lib/types'
import { useJobsStore } from '@/stores/jobsStore'

export default function BoardPage() {
  const { jobs, loading, error, fetchJobs, moveJob } = useJobsStore()

  useEffect(() => {
    void fetchJobs()
  }, [fetchJobs])

  const handleMove = (id: number, status: ApplicationStatus) => {
    moveJob(id, status).catch((e) => toast.error(`Não foi possível mover para "${STATUS_LABEL[status]}": ${errorMessage(e)}`))
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Candidaturas</h1>
          <p className="text-sm text-muted-foreground">Arraste os cards para mudar o status. Clique no cargo para abrir a vaga.</p>
        </div>
        <NewJobDialog />
      </div>

      {error && <ErrorAlert title="Não foi possível carregar as vagas" message={error} />}
      {loading && jobs.length === 0 && <Loading message="Carregando vagas…" />}
      {!loading && !error && jobs.length === 0 && (
        <div className="rounded-xl border border-dashed bg-background p-8 text-center text-sm text-muted-foreground">
          Nenhuma vaga ainda. Clique em <strong>Nova vaga</strong> e cole o texto de uma vaga para começar.
        </div>
      )}
      {jobs.length > 0 && <KanbanBoard jobs={jobs} onMove={handleMove} />}
    </div>
  )
}
