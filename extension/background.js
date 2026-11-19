// job-copilot: sends the job page open in the browser to the local backend.
// Only runs when the user clicks the extension button, and reads only the current tab
// (what the user is already seeing): no crawling, no requests to the job site.

const API_URL = 'http://localhost:8000' // backend (uvicorn)
const APP_URL = 'http://localhost:5173' // frontend (vite)

chrome.action.onClicked.addListener(async (tab) => {
  await setBadge('…', '#6b7280', 'Enviando a vaga…')
  try {
    const [{ result: page }] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: readPage })
    if (!page || page.text.trim().length < 100) {
      throw new Error('Não encontrei o texto da vaga nesta página. Selecione o texto da vaga e clique de novo.')
    }

    const response = await fetch(`${API_URL}/jobs/import`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(page),
    })
    const body = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(detailMessage(body.detail) || `O backend respondeu ${response.status}.`)

    await setBadge('OK', '#16a34a', body.created ? 'Vaga adicionada ao quadro' : 'Essa vaga já estava no quadro')
    await chrome.tabs.create({ url: `${APP_URL}/vagas/${body.job_id}` })
  } catch (error) {
    const offline = error instanceof TypeError // fetch failed: backend not running
    const message = offline
      ? 'Não consegui falar com o job-copilot. Confira se o backend está rodando (uvicorn) na porta 8000.'
      : String(error.message || error)
    await setBadge('ERRO', '#dc2626', message)
    await showInPage(tab.id, message)
  }
})

/** Runs inside the page: the selected text, or the job description area, or the whole page. */
function readPage() {
  const selection = String(window.getSelection() || '').trim()
  let text = selection
  if (text.length < 200) {
    // Job description containers of common sites (LinkedIn first); the rest falls back to main/body.
    const selectors = [
      '.jobs-search__job-details--container',
      '.jobs-details',
      '.job-view-layout',
      '[data-testid="job-details"]',
      '#job-description',
      'main',
      'article',
    ]
    const area = selectors
      .map((selector) => document.querySelector(selector))
      .find((element) => element && element.innerText.trim().length > 300)
    text = (area || document.body).innerText
  }
  return { url: location.href, title: document.title, text: text.trim().slice(0, 50000) }
}

function detailMessage(detail) {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((item) => item.msg).filter(Boolean).join(' ')
  return null
}

async function setBadge(text, color, title) {
  await chrome.action.setBadgeText({ text })
  await chrome.action.setBadgeBackgroundColor({ color })
  await chrome.action.setTitle({ title: `job-copilot: ${title}` })
  if (text === 'OK') setTimeout(() => chrome.action.setBadgeText({ text: '' }), 4000)
}

async function showInPage(tabId, message) {
  try {
    await chrome.scripting.executeScript({ target: { tabId }, func: (m) => alert(`job-copilot: ${m}`), args: [message] })
  } catch {
    // pages like chrome:// don't accept scripts; the badge title still has the message
  }
}
