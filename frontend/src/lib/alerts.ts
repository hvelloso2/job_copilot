import type { AlertCheck } from './types'

export const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

/** One-line summary of a check of the alert emails, for the toast. */
export function checkSummary(result: AlertCheck): string {
  if (result.emails_read === 0) return 'Nenhum e-mail de alerta novo.'
  const parts = [plural(result.emails_read, 'e-mail lido', 'e-mails lidos'), plural(result.leads_new, 'vaga nova', 'vagas novas')]
  if (result.leads_known) parts.push(`${plural(result.leads_known, 'repetida', 'repetidas')} de e-mails anteriores`)
  return parts.join(', ') + '.'
}
