import { Badge } from '@/components/ui/badge'
import { WORK_MODE_LABEL } from '@/lib/format'
import type { JobData } from '@/lib/types'

function List({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null
  return (
    <div>
      <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title} ({items.length})
      </h4>
      <ul className="list-disc space-y-0.5 pl-5 text-sm">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  )
}

/** The data Claude extracted from a posting (one track). */
export function JobDataView({ data }: { data: JobData }) {
  const facts = [
    data.company && `Empresa: ${data.company}`,
    data.seniority && `Senioridade: ${data.seniority}`,
    data.work_mode && `Modalidade: ${WORK_MODE_LABEL[data.work_mode]}`,
    data.location && `Local: ${data.location}`,
    data.salary && `Salário: ${data.salary}`,
  ].filter((fact): fact is string => Boolean(fact))

  return (
    <div className="space-y-4">
      <div>
        <p className="font-medium">{data.title}</p>
        <div className="mt-1 flex flex-wrap gap-1.5">
          {facts.map((fact) => (
            <Badge key={fact} variant="secondary">
              {fact}
            </Badge>
          ))}
        </div>
      </div>
      <List title="Requisitos obrigatórios" items={data.required_requirements} />
      <List title="Requisitos desejáveis" items={data.preferred_requirements} />
      {data.technologies.length > 0 && (
        <div>
          <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Tecnologias</h4>
          <div className="flex flex-wrap gap-1.5">
            {data.technologies.map((tech) => (
              <Badge key={tech} variant="outline">
                {tech}
              </Badge>
            ))}
          </div>
        </div>
      )}
      <List title="Responsabilidades" items={data.responsibilities} />
      <List title="Benefícios" items={data.benefits} />
    </div>
  )
}
