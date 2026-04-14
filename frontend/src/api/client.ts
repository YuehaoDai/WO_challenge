import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 120000,
})

export interface HistoryMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface AskRequest {
  question: string
  symbol?: string
  top_k?: number
  lang?: string
  history?: HistoryMessage[]
}

export interface Citation {
  chunk_id: string
  fiscal_year: number
  section_title: string
  snippet: string
  evidence_index: number
}

export interface AskResponse {
  query_type: string
  answer: string
  citations: Citation[]
  confidence: string
  debug: {
    query_type: string
    retrieval_time_ms: number
    fts_hits: number
    dense_hits: number
    after_rrf: number
    after_rerank: number
    context_chunks: number
    generation_time_ms: number
    total_time_ms: number
  }
}

export interface TrendPoint {
  fiscal_year: number
  value: number
  yoy_change: number | null
  yoy_pct: number | null
}

export interface TrendsResponse {
  symbol: string
  metric: string
  unit: string
  data: TrendPoint[]
  cagr: number | null
}

export interface SystemStatus {
  status: string
  go_backend: string
  python_service: string
  models_ready: boolean
  embedding_ready: boolean
  reranker_ready: boolean
  llm_provider: string
  chunks_count: number
  metrics_count: number
  fiscal_years: number[]
}

export async function ask(req: AskRequest): Promise<AskResponse> {
  const { data } = await api.post('/ask', req)
  return data
}

export interface StreamCallbacks {
  onMetadata?: (data: { query_type: string; confidence: string; debug: AskResponse['debug'] }) => void
  onCitations?: (citations: Citation[]) => void
  onToken?: (content: string) => void
  onDone?: (debug: AskResponse['debug']) => void
  onError?: (message: string) => void
}

export async function askStream(req: AskRequest, callbacks: StreamCallbacks): Promise<void> {
  const baseURL = api.defaults.baseURL || '/api/v1'
  const resp = await fetch(`${baseURL}/ask/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })

  if (!resp.ok) {
    const text = await resp.text()
    callbacks.onError?.(text || `HTTP ${resp.status}`)
    return
  }

  const reader = resp.body?.getReader()
  if (!reader) {
    callbacks.onError?.('ReadableStream not supported')
    return
  }

  const decoder = new TextDecoder()
  let buffer = ''
  let streamComplete = false

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    let currentEvent = ''
    for (const line of lines) {
      if (line.startsWith('event: ')) {
        currentEvent = line.slice(7).trim()
      } else if (line.startsWith('data: ')) {
        const payload = line.slice(6)
        try {
          const data = JSON.parse(payload)
          switch (currentEvent || data.type) {
            case 'metadata':
              callbacks.onMetadata?.(data)
              break
            case 'citations':
              callbacks.onCitations?.(data.citations)
              break
            case 'token':
              callbacks.onToken?.(data.content)
              break
            case 'done':
              callbacks.onDone?.(data.debug)
              streamComplete = true
              break
            case 'error':
              callbacks.onError?.(data.message)
              streamComplete = true
              break
          }
        } catch { /* incomplete JSON, skip */ }
        currentEvent = ''
      }
    }

    if (streamComplete) {
      reader.cancel().catch(() => {})
      break
    }
  }
}

export async function getTrends(metric: string, startYear = 2020, endYear = 2025): Promise<TrendsResponse> {
  const { data } = await api.get('/trends', { params: { metric, start_year: startYear, end_year: endYear } })
  return data
}

export async function getMetrics(metric: string, year?: number) {
  const { data } = await api.get('/metrics', { params: { metric, year } })
  return data
}

export async function getSections() {
  const { data } = await api.get('/sections')
  return data
}

export async function getSystemStatus(): Promise<SystemStatus> {
  const { data } = await api.get('/system/status')
  return data
}

export async function getAvailableMetrics(): Promise<string[]> {
  const { data } = await api.get('/metrics/available')
  return data.metrics || []
}

export default api
