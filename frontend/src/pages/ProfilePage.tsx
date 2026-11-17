import { FileUp, Save } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'

import { ErrorAlert, Loading } from '@/components/common'
import { ProfileEditor } from '@/components/profile/ProfileEditor'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { api, errorMessage } from '@/lib/api'
import { formatDateTime } from '@/lib/format'
import { missingRequired } from '@/lib/profile'
import type { ProfileData, ProfileOut } from '@/lib/types'

const EMPTY: ProfileData = {
  summary: null,
  experiences: [],
  skills: [],
  projects: [],
  education: [],
  certifications: [],
  languages: [],
}

export default function ProfilePage() {
  const fileInput = useRef<HTMLInputElement>(null)
  const [saved, setSaved] = useState<ProfileOut | null>(null)
  const [data, setData] = useState<ProfileData | null>(null)
  const [rawText, setRawText] = useState('')
  const [fromUpload, setFromUpload] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .getProfile()
      .then((profile) => {
        setSaved(profile)
        if (profile) {
          setData(profile.data)
          setRawText(profile.raw_text)
        }
      })
      .catch((e) => setError(errorMessage(e)))
      .finally(() => setLoading(false))
  }, [])

  const upload = async (file: File) => {
    if (dirty && !window.confirm('Você tem alterações não salvas. Substituir pelo perfil extraído do PDF?')) return
    setBusy('Lendo o currículo e extraindo o perfil com o Claude… (pode levar até 1 minuto)')
    setError(null)
    try {
      const draft = await api.uploadProfile(file)
      setData(draft.data)
      setRawText(draft.raw_text)
      setFromUpload(true)
      setDirty(true)
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(null)
      if (fileInput.current) fileInput.current.value = ''
    }
  }

  const save = async () => {
    if (!data) return
    const missing = missingRequired(data)
    if (missing.length) {
      setError(`Preencha os campos obrigatórios: ${missing.join('; ')}.`)
      return
    }
    setBusy('Salvando…')
    setError(null)
    try {
      const profile = await api.saveProfile(data, rawText)
      setSaved(profile)
      setData(profile.data)
      setFromUpload(false)
      setDirty(false)
      toast.success(`Perfil salvo (versão ${profile.version}).`)
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(null)
    }
  }

  if (loading) return <Loading message="Carregando perfil…" />

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Perfil</h1>
          <p className="text-sm text-muted-foreground">
            {saved
              ? `Versão ${saved.version}, salva em ${formatDateTime(saved.updated_at)}. É a única fonte de verdade sobre você: a IA não usa nada que não esteja aqui.`
              : 'Nenhum perfil salvo ainda. Comece enviando o seu currículo em PDF.'}
          </p>
        </div>
        <div className="flex gap-2">
          <input
            ref={fileInput}
            type="file"
            accept="application/pdf,.pdf"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) void upload(file)
            }}
          />
          <Button variant="outline" onClick={() => fileInput.current?.click()} disabled={Boolean(busy)}>
            <FileUp />
            Enviar currículo (PDF)
          </Button>
          {!data && (
            <Button variant="ghost" onClick={() => setData(EMPTY)} disabled={Boolean(busy)}>
              Preencher manualmente
            </Button>
          )}
        </div>
      </div>

      {busy && <Loading message={busy} />}
      {error && <ErrorAlert message={error} />}

      {fromUpload && (
        <Alert>
          <AlertTitle>Revise antes de salvar</AlertTitle>
          <AlertDescription>
            Este perfil foi extraído do PDF e ainda não foi salvo. Corrija o que estiver errado e apague o que não for
            verdade: tudo o que ficar aqui pode aparecer nas suas candidaturas.
          </AlertDescription>
        </Alert>
      )}

      {data && (
        <Card>
          <CardHeader>
            <CardTitle>Dados do perfil</CardTitle>
            <CardDescription>Itens de listas (atividades, skills, tecnologias) ficam um por linha.</CardDescription>
          </CardHeader>
          <CardContent>
            <ProfileEditor
              value={data}
              onChange={(next) => {
                setData(next)
                setDirty(true)
              }}
            />
          </CardContent>
        </Card>
      )}

      {rawText && (
        <details className="text-sm">
          <summary className="cursor-pointer text-muted-foreground">Texto lido do PDF</summary>
          <p className="mt-2 whitespace-pre-wrap rounded-lg bg-background p-3 text-xs">{rawText}</p>
        </details>
      )}

      {data && (
        <div className="sticky bottom-4 flex items-center justify-end gap-3 rounded-xl border bg-background/95 p-3 shadow-sm backdrop-blur">
          {dirty && <span className="text-sm text-muted-foreground">Alterações não salvas</span>}
          <Button onClick={save} disabled={!dirty || Boolean(busy)}>
            <Save />
            Salvar perfil
          </Button>
        </div>
      )}
    </div>
  )
}
