import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from '@dnd-kit/core'
import { useState } from 'react'

import { STATUS_LABEL, STATUS_ORDER } from '@/lib/format'
import type { ApplicationStatus, JobSummary } from '@/lib/types'
import { cn } from '@/lib/utils'

import { JobCard } from './JobCard'

function DraggableCard({ job }: { job: JobSummary }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: job.id })
  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      className={cn('cursor-grab touch-none active:cursor-grabbing', isDragging && 'opacity-30')}
    >
      <JobCard job={job} />
    </div>
  )
}

function Column({ status, jobs }: { status: ApplicationStatus; jobs: JobSummary[] }) {
  const { setNodeRef, isOver } = useDroppable({ id: status })
  return (
    <div
      ref={setNodeRef}
      className={cn(
        'flex w-64 shrink-0 flex-col rounded-xl border bg-muted/50 transition-colors',
        isOver && 'border-primary/40 bg-primary/5',
      )}
    >
      <div className="flex items-center justify-between px-3 py-2">
        <h2 className="text-sm font-semibold">{STATUS_LABEL[status]}</h2>
        <span className="rounded-full bg-background px-2 text-xs text-muted-foreground">{jobs.length}</span>
      </div>
      <div className="flex min-h-24 flex-1 flex-col gap-2 p-2 pt-0">
        {jobs.map((job) => (
          <DraggableCard key={job.id} job={job} />
        ))}
      </div>
    </div>
  )
}

export function KanbanBoard({
  jobs,
  onMove,
}: {
  jobs: JobSummary[]
  onMove: (id: number, status: ApplicationStatus) => void
}) {
  const [activeId, setActiveId] = useState<number | null>(null)
  // A small distance lets a click on the title open the job instead of starting a drag.
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor),
  )
  const active = jobs.find((job) => job.id === activeId) ?? null

  const handleDragStart = (event: DragStartEvent) => setActiveId(Number(event.active.id))
  const handleDragEnd = (event: DragEndEvent) => {
    setActiveId(null)
    const status = event.over?.id as ApplicationStatus | undefined
    if (status) onMove(Number(event.active.id), status)
  }

  return (
    <DndContext
      sensors={sensors}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragCancel={() => setActiveId(null)}
    >
      <div className="flex gap-3 overflow-x-auto pb-4">
        {STATUS_ORDER.map((status) => (
          <Column key={status} status={status} jobs={jobs.filter((job) => job.status === status)} />
        ))}
      </div>
      <DragOverlay>{active ? <JobCard job={active} dragging /> : null}</DragOverlay>
    </DndContext>
  )
}
