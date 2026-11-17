import type { ApplicationStatus, RequirementStatus, TextFormat, TextType, WorkMode } from './types'

export const STATUS_ORDER: ApplicationStatus[] = ['saved', 'applied', 'test', 'interview', 'offer', 'closed']

export const STATUS_LABEL: Record<ApplicationStatus, string> = {
  saved: 'Salva',
  applied: 'Aplicada',
  test: 'Teste',
  interview: 'Entrevista',
  offer: 'Oferta',
  closed: 'Encerrada',
}

export const REQUIREMENT_LABEL: Record<RequirementStatus, string> = {
  meets: 'Atende',
  partial: 'Parcial',
  missing: 'Não atende',
}

export const REQUIREMENT_CLASS: Record<RequirementStatus, string> = {
  meets: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  partial: 'bg-amber-100 text-amber-800 border-amber-200',
  missing: 'bg-red-100 text-red-800 border-red-200',
}

export const WORK_MODE_LABEL: Record<WorkMode, string> = {
  remote: 'Remoto',
  hybrid: 'Híbrido',
  onsite: 'Presencial',
}

export const TEXT_TYPE_LABEL: Record<TextType, string> = {
  summary: 'Resumo para o currículo',
  cover_letter: 'Carta de apresentação',
  answer: 'Resposta a uma pergunta',
}

export const TEXT_FORMAT_LABEL: Record<TextFormat, string> = {
  written: 'Texto escrito',
  audio_script: 'Roteiro para áudio',
}

/** The backend stores UTC datetimes without a timezone suffix; read them as UTC. */
export function parseApiDate(value: string): Date {
  return new Date(/(Z|[+-]\d\d:\d\d)$/.test(value) ? value : `${value}Z`)
}

export function daysSince(value: string, now: Date = new Date()): number {
  const diff = now.getTime() - parseApiDate(value).getTime()
  return Math.max(0, Math.floor(diff / 86_400_000))
}

export function daysAgoLabel(days: number): string {
  if (days === 0) return 'hoje'
  if (days === 1) return 'há 1 dia'
  return `há ${days} dias`
}

export function formatDate(value: string): string {
  return parseApiDate(value).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

export function formatDateTime(value: string): string {
  return parseApiDate(value).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

/** Color of a compatibility score (0-100). */
export function scoreClass(score: number | null): string {
  if (score === null) return 'bg-muted text-muted-foreground border-border'
  if (score >= 70) return 'bg-emerald-100 text-emerald-800 border-emerald-200'
  if (score >= 40) return 'bg-amber-100 text-amber-800 border-amber-200'
  return 'bg-red-100 text-red-800 border-red-200'
}
