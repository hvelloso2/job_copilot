import type { ProfileData } from './types'

/** "One item per line" text to a list, ignoring blank lines. */
export function parseLines(raw: string): string[] {
  return raw
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

/** Required fields left empty; the backend would reject them. */
export function missingRequired(data: ProfileData): string[] {
  const missing: string[] = []
  data.experiences.forEach((e, i) => {
    if (!e.title.trim() || !e.company.trim()) missing.push(`Experiência ${i + 1}: cargo e empresa`)
  })
  data.skills.forEach((s, i) => !s.category.trim() && missing.push(`Skills ${i + 1}: categoria`))
  data.projects.forEach((p, i) => !p.name.trim() && missing.push(`Projeto ${i + 1}: nome`))
  data.education.forEach((e, i) => !e.institution.trim() && missing.push(`Formação ${i + 1}: instituição`))
  data.certifications.forEach((c, i) => !c.name.trim() && missing.push(`Certificação ${i + 1}: nome`))
  data.languages.forEach((l, i) => !l.language.trim() && missing.push(`Idioma ${i + 1}: idioma`))
  return missing
}
