import { Save } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { ErrorAlert, Section } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { api, errorMessage } from '@/lib/api'
import { formatDateTime, STATUS_LABEL } from '@/lib/format'
import type { JobOut } from '@/lib/types'

export function NotesPanel({ job, onSaved }: { job: JobOut; onSaved: (job: JobOut) => void }) {
  const [notes, setNotes] = useState(job.notes)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const dirty = notes !== job.notes

  const save = async () => {
    setBusy(true)
    setError(null)
    try {
      onSaved(await api.updateApplication(job.id, { notes }))
      toast.success('Notas salvas.')
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid gap-6 md:grid-cols-[2fr_1fr]">
      <Section title="Notas" description="Contatos, datas de entrevista, impressões, próximos passos…">
        <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={10} disabled={busy} />
        <div className="flex items-center gap-3">
          <Button onClick={save} disabled={!dirty || busy}>
            <Save />
            Salvar notas
          </Button>
          {dirty && <span className="text-xs text-muted-foreground">Alterações não salvas</span>}
        </div>
        {error && <ErrorAlert message={error} />}
      </Section>
      <Section title="Histórico de status">
        <ol className="space-y-2 border-l pl-4 text-sm">
          {[...job.status_history].reverse().map((h, i) => (
            <li key={i}>
              <span className="font-medium">{STATUS_LABEL[h.status] ?? h.status}</span>
              <span className="block text-xs text-muted-foreground">{formatDateTime(h.at)}</span>
            </li>
          ))}
        </ol>
      </Section>
    </div>
  )
}
