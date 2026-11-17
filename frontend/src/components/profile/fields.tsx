import { Plus, Trash2 } from 'lucide-react'
import { useState, type ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { parseLines } from '@/lib/profile'

function sameList(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((item, i) => item === b[i])
}

/**
 * A list of strings edited as "one item per line". Keeps the raw text locally so that typing a
 * new line (still empty) works; only re-syncs when the list changes from outside.
 */
export function LinesField({
  label,
  value,
  onChange,
  rows = 3,
  hint = 'Um item por linha',
}: {
  label: string
  value: string[]
  onChange: (value: string[]) => void
  rows?: number
  hint?: string
}) {
  const [raw, setRaw] = useState(value.join('\n'))
  const [lastValue, setLastValue] = useState(value)
  // The list changed from outside (e.g. a new PDF was uploaded): show it.
  if (value !== lastValue) {
    setLastValue(value)
    if (!sameList(parseLines(raw), value)) setRaw(value.join('\n'))
  }

  return (
    <div className="space-y-1.5">
      <Label>
        {label} <span className="font-normal text-muted-foreground">({hint.toLowerCase()})</span>
      </Label>
      <Textarea
        aria-label={label}
        value={raw}
        rows={rows}
        onChange={(e) => {
          setRaw(e.target.value)
          onChange(parseLines(e.target.value))
        }}
      />
    </div>
  )
}

/** Text input for an optional field: an empty value is saved as null. */
export function TextField({
  label,
  value,
  onChange,
  required = false,
}: {
  label: string
  value: string | null
  onChange: (value: string | null) => void
  required?: boolean
}) {
  return (
    <div className="space-y-1.5">
      <Label>
        {label}
        {required && <span className="text-red-600"> *</span>}
      </Label>
      <Input
        aria-label={label}
        value={value ?? ''}
        onChange={(e) => onChange(required ? e.target.value : e.target.value || null)}
      />
    </div>
  )
}

/** A section with a list of items that can be added and removed. */
export function ListSection<T>({
  title,
  items,
  onChange,
  newItem,
  addLabel,
  render,
}: {
  title: string
  items: T[]
  onChange: (items: T[]) => void
  newItem: () => T
  addLabel: string
  render: (item: T, update: (item: T) => void) => ReactNode
}) {
  return (
    <section className="space-y-3">
      <h3 className="text-sm font-semibold">
        {title} <span className="font-normal text-muted-foreground">({items.length})</span>
      </h3>
      {items.map((item, i) => (
        <div key={i} className="relative space-y-3 rounded-lg border bg-background p-4 pr-12">
          {render(item, (updated) => onChange(items.map((it, j) => (j === i ? updated : it))))}
          <Button
            variant="ghost"
            size="icon-sm"
            className="absolute top-2 right-2"
            aria-label={`Remover de ${title}`}
            onClick={() => onChange(items.filter((_, j) => j !== i))}
          >
            <Trash2 />
          </Button>
        </div>
      ))}
      <Button variant="outline" size="sm" onClick={() => onChange([...items, newItem()])}>
        <Plus />
        {addLabel}
      </Button>
    </section>
  )
}
