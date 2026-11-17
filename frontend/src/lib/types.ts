// Types of the FastAPI backend responses (see backend/app/schemas.py and backend/app/llm/schemas.py).

export type ApplicationStatus = 'saved' | 'applied' | 'test' | 'interview' | 'offer' | 'closed'
export type WorkMode = 'remote' | 'hybrid' | 'onsite'
export type RequirementStatus = 'meets' | 'partial' | 'missing'
export type RequirementKind = 'required' | 'preferred'
export type TextType = 'summary' | 'cover_letter' | 'answer'
export type TextFormat = 'written' | 'audio_script'

// --- Profile ---

export interface Experience {
  title: string
  company: string
  period: string | null
  activities: string[]
}

export interface SkillCategory {
  category: string
  items: string[]
}

export interface Project {
  name: string
  description: string | null
  technologies: string[]
  link: string | null
}

export interface Education {
  institution: string
  degree: string | null
  period: string | null
}

export interface Certification {
  name: string
  issuer: string | null
  year: string | null
}

export interface Language {
  language: string
  level: string | null
}

export interface ProfileData {
  summary: string | null
  experiences: Experience[]
  skills: SkillCategory[]
  projects: Project[]
  education: Education[]
  certifications: Certification[]
  languages: Language[]
}

export interface ProfileDraft {
  data: ProfileData
  raw_text: string
}

export interface ProfileOut extends ProfileDraft {
  version: number
  updated_at: string
}

// --- Jobs ---

export interface JobData {
  company: string | null
  title: string
  seniority: string | null
  work_mode: WorkMode | null
  location: string | null
  required_requirements: string[]
  preferred_requirements: string[]
  technologies: string[]
  responsibilities: string[]
  benefits: string[]
  salary: string | null
}

export interface JobSummary {
  id: number
  company: string
  title: string
  status: ApplicationStatus
  needs_track_choice: boolean
  score: number | null
  created_at: string
  updated_at: string
}

export interface JobOut extends JobSummary {
  url: string | null
  raw_text: string
  tracks: JobData[]
  selected_track: number | null
  status_history: { status: ApplicationStatus; at: string }[]
  notes: string
}

// --- Analysis ---

export interface RequirementResult {
  requirement: string
  kind: RequirementKind
  status: RequirementStatus
  model_status: RequirementStatus | null
  evidence: string | null
  evidence_verified: boolean
  explanation: string
  note: string | null
}

export interface StrengthResult {
  point: string
  evidence: string
  evidence_verified: boolean
}

export interface SuggestionResult {
  original: string
  suggested: string
  reason: string
  original_found: boolean
  unsupported: string[]
}

export interface AnalysisOut {
  id: number
  job_id: number
  track: number
  track_title: string
  score: number | null
  requirements: RequirementResult[]
  strengths: StrengthResult[]
  gaps: string[]
  resume_suggestions: SuggestionResult[]
  study_plan: string[]
  verification: {
    evidence_rejected: number
    requirements_not_assessed: number
    strengths_rejected: number
    suggestions_flagged: number
  }
  profile_version: number
  outdated: boolean
  created_at: string
}

// --- Generated texts ---

export interface ClaimResult {
  claim: string
  evidence: string | null
  supported: boolean
  reason: string | null
  start: number | null
  end: number | null
}

export interface TextOut {
  id: number
  job_id: number
  type: TextType
  format: TextFormat
  question: string | null
  text: string
  highlighted_text: string
  placeholders: string[]
  claims: ClaimResult[]
  unsupported_claims: number
  warnings: string[]
  profile_version: number
  analysis_id: number
  created_at: string
}

export interface TextRequest {
  type: TextType
  question?: string
  format?: TextFormat
}
