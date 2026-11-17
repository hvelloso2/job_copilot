import { AlertTriangle, Clock } from 'lucide-react'
import { Link } from 'react-router-dom'

import { ColorBadge } from '@/components/common'
import { daysAgoLabel, daysSince, scoreClass } from '@/lib/format'
import type { JobSummary } from '@/lib/types'
import { cn } from '@/lib/utils'

export function JobCard({ job, dragging = false }: { job: JobSummary; dragging?: boolean }) {
  return (
    <div
      className={cn(
        'rounded-lg border bg-card p-3 text-left shadow-xs transition-shadow',
        dragging ? 'rotate-1 shadow-lg ring-2 ring-primary/30' : 'hover:shadow-sm',
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-xs text-muted-foreground">{job.company || 'Empresa não informada'}</p>
          <Link
            to={`/vagas/${job.id}`}
            className="line-clamp-2 text-sm font-medium hover:underline"
            onPointerDown={(e) => e.stopPropagation()}
          >
            {job.title || 'Vaga sem título'}
          </Link>
        </div>
        <ColorBadge className={scoreClass(job.score)}>{job.score === null ? '—' : job.score}</ColorBadge>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <Clock className="size-3" />
          {daysAgoLabel(daysSince(job.updated_at))}
        </span>
        {job.score === null && !job.needs_track_choice && <span>sem análise</span>}
        {job.needs_track_choice && (
          <span className="inline-flex items-center gap-1 text-amber-700">
            <AlertTriangle className="size-3" />
            escolher trilha
          </span>
        )}
      </div>
    </div>
  )
}
