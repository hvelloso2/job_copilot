import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

export interface BarItem {
  key: string
  label: ReactNode
  value: number
  /** Text shown at the end of the bar (e.g. "3 vagas · 60%"). */
  valueLabel: string
  /** Tooltip on hover. */
  tooltip: string
  /** Tailwind classes of the filled part. */
  barClass?: string
}

/**
 * Horizontal bar chart: one row per item, bars on a shared 0..max scale.
 * Values are always written next to the bar, so color is never the only cue.
 */
export function BarList({ items, max, ariaLabel }: { items: BarItem[]; max?: number; ariaLabel: string }) {
  const scale = max ?? Math.max(1, ...items.map((item) => item.value))
  return (
    <ul className="space-y-1.5" aria-label={ariaLabel}>
      {items.map((item) => {
        const width = scale > 0 ? (100 * item.value) / scale : 0
        return (
          <li
            key={item.key}
            title={item.tooltip}
            className="grid grid-cols-[minmax(0,9rem)_1fr_auto] items-center gap-3 rounded-md px-1 py-0.5 text-sm hover:bg-muted/60 sm:grid-cols-[minmax(0,12rem)_1fr_auto]"
          >
            <span className="truncate">{item.label}</span>
            <span className="h-4 rounded-sm bg-muted">
              <span
                className={cn('block h-full rounded-r-[4px]', item.barClass ?? 'bg-primary/80')}
                style={{ width: `${width}%`, minWidth: item.value > 0 ? 4 : 0 }}
              />
            </span>
            <span className="text-right tabular-nums text-muted-foreground">{item.valueLabel}</span>
          </li>
        )
      })}
    </ul>
  )
}
