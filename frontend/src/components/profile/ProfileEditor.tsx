import { Separator } from '@/components/ui/separator'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import type { ProfileData } from '@/lib/types'

import { LinesField, ListSection, TextField } from './fields'

/** Editor for every section of the profile. Controlled: the parent owns the data. */
export function ProfileEditor({ value, onChange }: { value: ProfileData; onChange: (value: ProfileData) => void }) {
  const set = <K extends keyof ProfileData>(key: K, data: ProfileData[K]) => onChange({ ...value, [key]: data })

  return (
    <div className="space-y-8">
      <section className="space-y-1.5">
        <Label htmlFor="summary" className="text-sm font-semibold">
          Resumo
        </Label>
        <Textarea
          id="summary"
          value={value.summary ?? ''}
          rows={5}
          onChange={(e) => set('summary', e.target.value || null)}
        />
      </section>

      <Separator />
      <ListSection
        title="Experiências"
        addLabel="Adicionar experiência"
        items={value.experiences}
        onChange={(items) => set('experiences', items)}
        newItem={() => ({ title: '', company: '', period: null, activities: [] })}
        render={(exp, update) => (
          <>
            <div className="grid gap-3 sm:grid-cols-3">
              <TextField label="Cargo" required value={exp.title} onChange={(v) => update({ ...exp, title: v ?? '' })} />
              <TextField label="Empresa" required value={exp.company} onChange={(v) => update({ ...exp, company: v ?? '' })} />
              <TextField label="Período" value={exp.period} onChange={(v) => update({ ...exp, period: v })} />
            </div>
            <LinesField
              label="Atividades"
              rows={6}
              value={exp.activities}
              onChange={(activities) => update({ ...exp, activities })}
            />
          </>
        )}
      />

      <Separator />
      <ListSection
        title="Skills"
        addLabel="Adicionar categoria"
        items={value.skills}
        onChange={(items) => set('skills', items)}
        newItem={() => ({ category: '', items: [] })}
        render={(skill, update) => (
          <div className="grid gap-3 sm:grid-cols-[1fr_2fr]">
            <TextField label="Categoria" required value={skill.category} onChange={(v) => update({ ...skill, category: v ?? '' })} />
            <LinesField label="Skills" value={skill.items} onChange={(items) => update({ ...skill, items })} />
          </div>
        )}
      />

      <Separator />
      <ListSection
        title="Projetos"
        addLabel="Adicionar projeto"
        items={value.projects}
        onChange={(items) => set('projects', items)}
        newItem={() => ({ name: '', description: null, technologies: [], link: null })}
        render={(project, update) => (
          <>
            <div className="grid gap-3 sm:grid-cols-2">
              <TextField label="Nome" required value={project.name} onChange={(v) => update({ ...project, name: v ?? '' })} />
              <TextField label="Link" value={project.link} onChange={(v) => update({ ...project, link: v })} />
            </div>
            <div className="space-y-1.5">
              <Label>Descrição</Label>
              <Textarea
                aria-label="Descrição"
                value={project.description ?? ''}
                rows={3}
                onChange={(e) => update({ ...project, description: e.target.value || null })}
              />
            </div>
            <LinesField
              label="Tecnologias"
              value={project.technologies}
              onChange={(technologies) => update({ ...project, technologies })}
            />
          </>
        )}
      />

      <Separator />
      <ListSection
        title="Formação"
        addLabel="Adicionar formação"
        items={value.education}
        onChange={(items) => set('education', items)}
        newItem={() => ({ institution: '', degree: null, period: null })}
        render={(edu, update) => (
          <div className="grid gap-3 sm:grid-cols-3">
            <TextField label="Instituição" required value={edu.institution} onChange={(v) => update({ ...edu, institution: v ?? '' })} />
            <TextField label="Curso" value={edu.degree} onChange={(v) => update({ ...edu, degree: v })} />
            <TextField label="Período" value={edu.period} onChange={(v) => update({ ...edu, period: v })} />
          </div>
        )}
      />

      <Separator />
      <ListSection
        title="Certificações"
        addLabel="Adicionar certificação"
        items={value.certifications}
        onChange={(items) => set('certifications', items)}
        newItem={() => ({ name: '', issuer: null, year: null })}
        render={(cert, update) => (
          <div className="grid gap-3 sm:grid-cols-3">
            <TextField label="Nome" required value={cert.name} onChange={(v) => update({ ...cert, name: v ?? '' })} />
            <TextField label="Emissor" value={cert.issuer} onChange={(v) => update({ ...cert, issuer: v })} />
            <TextField label="Ano" value={cert.year} onChange={(v) => update({ ...cert, year: v })} />
          </div>
        )}
      />

      <Separator />
      <ListSection
        title="Idiomas"
        addLabel="Adicionar idioma"
        items={value.languages}
        onChange={(items) => set('languages', items)}
        newItem={() => ({ language: '', level: null })}
        render={(lang, update) => (
          <div className="grid gap-3 sm:grid-cols-2">
            <TextField label="Idioma" required value={lang.language} onChange={(v) => update({ ...lang, language: v ?? '' })} />
            <TextField label="Nível" value={lang.level} onChange={(v) => update({ ...lang, level: v })} />
          </div>
        )}
      />
    </div>
  )
}
