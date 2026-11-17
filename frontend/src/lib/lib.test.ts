import { afterEach, describe, expect, it, vi } from 'vitest'

import { api, ApiError, detailMessage } from './api'
import { daysAgoLabel, daysSince, parseApiDate, scoreClass } from './format'
import { parseHighlighted } from './highlight'

describe('parseHighlighted', () => {
  it('splits unsupported claims, placeholders and plain text', () => {
    const text = 'Uso Python e [[SEM SUPORTE: tenho 3 anos de Docker]]. Quero a vaga porque [PREENCHER: motivo].'
    expect(parseHighlighted(text)).toEqual([
      { kind: 'text', text: 'Uso Python e ' },
      { kind: 'unsupported', text: 'tenho 3 anos de Docker' },
      { kind: 'text', text: '. Quero a vaga porque ' },
      { kind: 'placeholder', text: '[PREENCHER: motivo]' },
      { kind: 'text', text: '.' },
    ])
  })

  it('returns the whole text when there is nothing to highlight', () => {
    expect(parseHighlighted('Tudo certo.')).toEqual([{ kind: 'text', text: 'Tudo certo.' }])
    expect(parseHighlighted('')).toEqual([])
  })
})

describe('dates', () => {
  it('reads backend datetimes without timezone as UTC', () => {
    expect(parseApiDate('2026-11-17T12:00:00').toISOString()).toBe('2026-11-17T12:00:00.000Z')
    expect(parseApiDate('2026-11-17T12:00:00+00:00').toISOString()).toBe('2026-11-17T12:00:00.000Z')
  })

  it('counts whole days since the last update', () => {
    const now = new Date('2026-11-17T12:00:00Z')
    expect(daysSince('2026-11-17T08:00:00', now)).toBe(0)
    expect(daysSince('2026-11-15T11:00:00', now)).toBe(2)
    expect(daysSince('2026-11-18T00:00:00', now)).toBe(0) // never negative
    expect([0, 1, 5].map(daysAgoLabel)).toEqual(['hoje', 'há 1 dia', 'há 5 dias'])
  })
})

describe('scoreClass', () => {
  it('uses green, amber and red bands', () => {
    expect(scoreClass(76)).toContain('emerald')
    expect(scoreClass(40)).toContain('amber')
    expect(scoreClass(39)).toContain('red')
    expect(scoreClass(null)).toContain('muted')
  })
})

describe('api errors', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('turns FastAPI details into readable messages', () => {
    expect(detailMessage('Vaga não encontrada.')).toBe('Vaga não encontrada.')
    expect(
      detailMessage([{ loc: ['body'], msg: "Value error, Envie a pergunta do processo seletivo em 'question'." }]),
    ).toBe("Envie a pergunta do processo seletivo em 'question'.")
    expect(detailMessage({ unexpected: true })).toBeNull()
  })

  it('throws ApiError with the backend message', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Salve o seu perfil antes de analisar uma vaga.' }), { status: 409 })))

    await expect(api.analyze(1)).rejects.toMatchObject({
      status: 409,
      message: 'Salve o seu perfil antes de analisar uma vaga.',
    })
  })

  it('explains when the backend is down', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('proxy error', { status: 500 })))
    await expect(api.listJobs()).rejects.toThrow(/backend está rodando/)

    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(api.listJobs()).rejects.toBeInstanceOf(ApiError)
  })

  it('maps 404 to null where "not found yet" is a normal state', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Nenhum perfil salvo ainda.' }), { status: 404 })))
    await expect(api.getProfile()).resolves.toBeNull()
  })

  it('sends JSON to the /api proxy', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 1 }), { status: 201 }))
    vi.stubGlobal('fetch', fetchMock)

    await api.generateText(3, { type: 'answer', question: 'Por quê?', format: 'audio_script' })

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/jobs/3/texts')
    expect(init.method).toBe('POST')
    expect(init.headers).toEqual({ 'Content-Type': 'application/json' })
    expect(JSON.parse(init.body)).toEqual({ type: 'answer', question: 'Por quê?', format: 'audio_script' })
  })
})
