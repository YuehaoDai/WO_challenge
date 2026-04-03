import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 120000,
})

export interface AskRequest {
  question: string
  symbol?: string
  top_k?: number
  lang?: string
}

export interface Citation {
  chunk_id: string
  fiscal_year: number
  section_title: string
  snippet: string
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
  chunks_count: number
  metrics_count: number
  fiscal_years: number[]
}

export async function ask(req: AskRequest): Promise<AskResponse> {
  const { data } = await api.post('/ask', req)
  return data
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
