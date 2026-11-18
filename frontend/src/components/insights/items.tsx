import { CheckCircle2, CircleAlert } from 'lucide-react'

import type { BarItem } from '@/components/insights/BarList'
import { STATUS_LABEL } from '@/lib/format'
import type { FunnelStep, SkillDemand, StatusScore } from '@/lib/types'

// Turns GET /insights data into rows of the dashboard bar charts.

const IN_PROFILE_BAR = 'bg-emerald-500/70 dark:bg-emerald-400/60'
const GAP_BAR = 'bg-red-500/80 dark:bg-red-400/70'

export const vagas = (n: number) => (n === 1 ? '1 vaga' : `${n} vagas`)

export function skillItems(skills: SkillDemand[]): BarItem[] {
  return skills.map((skill) => ({
    key: skill.name,
    label: (
      <span className="flex items-center gap-1.5">
        {skill.in_profile ? (
          <CheckCircle2 className="size-3.5 shrink-0 text-emerald-600 dark:text-emerald-400" aria-label="No perfil" />
        ) : (
          <CircleAlert className="size-3.5 shrink-0 text-red-600 dark:text-red-400" aria-label="Falta no perfil" />
        )}
        <span className="truncate">{skill.name}</span>
      </span>
    ),
    value: skill.count,
    valueLabel: `${vagas(skill.count)} · ${skill.share}%`,
    tooltip: `${skill.name}: pedida em ${vagas(skill.count)} (${skill.share}%). ${skill.in_profile ? 'Está no seu perfil.' : 'Não está no seu perfil.'}`,
    barClass: skill.in_profile ? IN_PROFILE_BAR : GAP_BAR,
  }))
}

export function funnelItems(funnel: FunnelStep[]): BarItem[] {
  return funnel
    .filter((step) => step.status !== 'closed')
    .map((step) => ({
      key: step.status,
      label: STATUS_LABEL[step.status],
      value: step.reached,
      valueLabel: step.rate_from_previous === null ? `${step.reached}` : `${step.reached} · ${step.rate_from_previous}%`,
      tooltip:
        `${STATUS_LABEL[step.status]}: ${step.reached} chegaram aqui ou passaram, ${step.current} estão aqui agora.` +
        (step.rate_from_previous === null ? '' : ` Avanço da etapa anterior: ${step.rate_from_previous}%.`),
    }))
}

export function scoreItems(scores: StatusScore[]): BarItem[] {
  return scores
    .filter((s) => s.total > 0)
    .map((s) => ({
      key: s.status,
      label: STATUS_LABEL[s.status],
      value: s.average ?? 0,
      valueLabel: s.average === null ? 'sem análise' : `${s.average} (${s.analyzed} de ${s.total})`,
      tooltip:
        s.average === null
          ? `${STATUS_LABEL[s.status]}: nenhuma das ${s.total} vagas foi analisada.`
          : `${STATUS_LABEL[s.status]}: nota média ${s.average}, de ${s.analyzed} vagas analisadas (de ${s.total}).`,
    }))
}
