import { parseHighlighted } from '@/lib/highlight'
import type { ClaimResult } from '@/lib/types'

/**
 * Shows a generated text with unsupported claims in red (hover shows why) and
 * [PREENCHER: ...] placeholders in yellow.
 */
export function HighlightedText({ value, claims }: { value: string; claims: ClaimResult[] }) {
  const reasons = new Map(claims.filter((c) => !c.supported).map((c) => [c.claim, c.reason ?? '']))
  return (
    <div className="whitespace-pre-wrap text-sm leading-relaxed">
      {parseHighlighted(value).map((segment, i) => {
        if (segment.kind === 'unsupported') {
          return (
            <mark
              key={i}
              data-kind="unsupported"
              title={`Sem suporte no perfil. ${reasons.get(segment.text) ?? ''}`.trim()}
              className="rounded bg-red-100 px-0.5 text-red-900 underline decoration-red-500 decoration-wavy underline-offset-4"
            >
              {segment.text}
            </mark>
          )
        }
        if (segment.kind === 'placeholder') {
          return (
            <mark key={i} data-kind="placeholder" className="rounded bg-amber-100 px-0.5 font-medium text-amber-900">
              {segment.text}
            </mark>
          )
        }
        return <span key={i}>{segment.text}</span>
      })}
    </div>
  )
}
