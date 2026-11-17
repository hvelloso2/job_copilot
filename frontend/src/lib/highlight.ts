/**
 * Splits a verified text into segments for display:
 * - "unsupported": a claim the backend could not verify, marked as [[SEM SUPORTE: ...]];
 * - "placeholder": something the user must fill in, written as [PREENCHER: ...];
 * - "text": everything else.
 */
export type Segment =
  | { kind: 'text'; text: string }
  | { kind: 'unsupported'; text: string }
  | { kind: 'placeholder'; text: string }

const MARKERS = /\[\[SEM SUPORTE: ([\s\S]*?)\]\]|\[PREENCHER:[^\]]*\]/g

export function parseHighlighted(value: string): Segment[] {
  const segments: Segment[] = []
  let cursor = 0
  for (const match of value.matchAll(MARKERS)) {
    const start = match.index ?? 0
    if (start > cursor) segments.push({ kind: 'text', text: value.slice(cursor, start) })
    if (match[1] !== undefined) segments.push({ kind: 'unsupported', text: match[1] })
    else segments.push({ kind: 'placeholder', text: match[0] })
    cursor = start + match[0].length
  }
  if (cursor < value.length) segments.push({ kind: 'text', text: value.slice(cursor) })
  return segments
}
