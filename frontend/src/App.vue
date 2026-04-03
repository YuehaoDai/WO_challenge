<template>
  <div class="app">
    <header class="header">
      <div class="header-left">
        <h1>AAPL 10-K Intelligence</h1>
        <span class="subtitle">2020–2025 SEC Filing Analysis</span>
      </div>
      <div class="header-right">
        <span class="status-dot" :class="systemOk ? 'ok' : 'err'"></span>
        <span class="status-text">{{ systemOk ? 'System Ready' : 'Connecting...' }}</span>
      </div>
    </header>

    <div class="main">
      <aside class="sidebar">
        <div class="section-group">
          <h3>Analysis Scenarios</h3>
          <button v-for="s in scenarios" :key="s.label" class="scenario-btn" @click="askQuestion(s.question)">
            <span class="scenario-icon">{{ s.icon }}</span>
            <span>{{ s.label }}</span>
          </button>
        </div>

        <div class="section-group">
          <h3>Financial Trends</h3>
          <select v-model="selectedMetric" @change="loadTrend" class="metric-select">
            <option value="">Select metric...</option>
            <option v-for="m in availableMetrics" :key="m" :value="m">{{ formatMetricName(m) }}</option>
          </select>
        </div>

        <div class="section-group">
          <h3>Custom Question</h3>
          <textarea v-model="customQuestion" placeholder="Ask about Apple's 10-K filings..." class="question-input" rows="3" @keydown.enter.ctrl="askQuestion(customQuestion)"></textarea>
          <button class="ask-btn" @click="askQuestion(customQuestion)" :disabled="loading || !customQuestion.trim()">
            {{ loading ? 'Analyzing...' : 'Analyze' }}
          </button>
        </div>
      </aside>

      <section class="content">
        <div v-if="loading" class="loading-overlay">
          <div class="spinner"></div>
          <p>Retrieving evidence and generating analysis...</p>
        </div>

        <div v-if="answer" class="answer-panel">
          <div class="answer-header">
            <span class="query-type-badge" :class="answer.query_type">{{ answer.query_type }}</span>
            <span class="confidence-badge" :class="answer.confidence">{{ answer.confidence }} confidence</span>
            <span class="timing">{{ answer.debug?.total_time_ms }}ms</span>
          </div>
          <div class="answer-body" v-html="formatAnswer(answer.answer)"></div>

          <div class="debug-bar" v-if="answer.debug">
            <span>FTS: {{ answer.debug.fts_hits }}</span>
            <span>Dense: {{ answer.debug.dense_hits }}</span>
            <span>RRF: {{ answer.debug.after_rrf }}</span>
            <span>Reranked: {{ answer.debug.after_rerank }}</span>
            <span>Context: {{ answer.debug.context_chunks }}</span>
            <span>Retrieval: {{ answer.debug.retrieval_time_ms }}ms</span>
            <span>Generation: {{ answer.debug.generation_time_ms }}ms</span>
          </div>
        </div>

        <div v-if="answer?.citations?.length" class="citations-panel">
          <h3>Evidence Sources</h3>
          <div v-for="(c, i) in answer.citations" :key="i" class="citation-card" @click="toggleCitation(i)">
            <div class="citation-header">
              <span class="citation-badge">FY{{ c.fiscal_year }}</span>
              <span class="citation-section">{{ c.section_title }}</span>
              <span class="citation-id">{{ c.chunk_id }}</span>
            </div>
            <div v-if="expandedCitation === i" class="citation-body">{{ c.snippet }}</div>
          </div>
        </div>

        <div v-if="trendData" class="trend-panel">
          <h3>{{ formatMetricName(selectedMetric) }} — AAPL FY2020–2025</h3>
          <div class="chart-container" ref="chartRef"></div>
          <div v-if="trendData.cagr !== null" class="cagr-badge">
            CAGR: {{ trendData.cagr }}%
          </div>
          <table class="trend-table">
            <thead>
              <tr><th>Fiscal Year</th><th>Value</th><th>YoY Change</th><th>YoY %</th></tr>
            </thead>
            <tbody>
              <tr v-for="d in trendData.data" :key="d.fiscal_year">
                <td>{{ d.fiscal_year }}</td>
                <td>{{ formatValue(d.value, trendData.unit) }}</td>
                <td>{{ d.yoy_change != null ? formatValue(d.yoy_change, trendData.unit) : '—' }}</td>
                <td :class="d.yoy_pct > 0 ? 'positive' : d.yoy_pct < 0 ? 'negative' : ''">
                  {{ d.yoy_pct != null ? d.yoy_pct.toFixed(1) + '%' : '—' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="!answer && !trendData && !loading" class="empty-state">
          <h2>Apple 10-K Filing Intelligence</h2>
          <p>Select an analysis scenario or ask a custom question to analyze Apple's SEC 10-K filings from 2020 to 2025.</p>
          <div class="capabilities">
            <div class="cap-item">
              <strong>Narrative Q&A</strong>
              <span>Business strategy, risk factors, management discussion</span>
            </div>
            <div class="cap-item">
              <strong>Financial Metrics</strong>
              <span>Revenue, margins, EPS with deterministic calculations</span>
            </div>
            <div class="cap-item">
              <strong>Cross-Year Comparison</strong>
              <span>Compare risk themes, strategy shifts across years</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import { ask, getTrends, getSystemStatus, type AskResponse, type TrendsResponse } from './api/client'

const scenarios = [
  { icon: '📊', label: 'Business Overview', question: "What are Apple's main business segments and products as described in the most recent 10-K?" },
  { icon: '⚠️', label: 'Key Risk Factors', question: "What are the most significant risk factors Apple disclosed in its 2025 10-K filing?" },
  { icon: '💰', label: 'Revenue Analysis', question: "What was Apple's net sales and how did it change compared to the prior year?" },
  { icon: '📈', label: 'Profitability Trends', question: "Compare Apple's gross margin and operating income trends from 2020 to 2025" },
  { icon: '🌍', label: 'Tariff & Trade Impact', question: "How does Apple describe the impact of tariffs and trade restrictions in recent filings?" },
  { icon: '🔬', label: 'R&D Investment', question: "How has Apple's research and development spending changed from 2020 to 2025?" },
  { icon: '💵', label: 'Capital Return', question: "Summarize Apple's share repurchase and dividend activity across 2020-2025" },
  { icon: '📱', label: 'Product Strategy', question: "How has Apple's product lineup evolved based on the Business section across multiple years?" },
]

const availableMetrics = ref<string[]>([
  'net_sales', 'gross_profit', 'operating_income', 'net_income',
  'eps_diluted', 'rd_expense', 'total_assets', 'total_liabilities',
  'long_term_debt', 'operating_cash_flow', 'share_repurchases',
])

const customQuestion = ref('')
const loading = ref(false)
const answer = ref<AskResponse | null>(null)
const trendData = ref<TrendsResponse | null>(null)
const selectedMetric = ref('')
const expandedCitation = ref<number | null>(null)
const systemOk = ref(false)
const chartRef = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null

onMounted(async () => {
  try {
    await getSystemStatus()
    systemOk.value = true
  } catch { systemOk.value = false }
})

async function askQuestion(question: string) {
  if (!question.trim()) return
  loading.value = true
  answer.value = null
  trendData.value = null
  expandedCitation.value = null
  try {
    answer.value = await ask({ question })
  } catch (e: any) {
    answer.value = {
      query_type: 'error', answer: `Error: ${e.message || 'Request failed'}`,
      citations: [], confidence: 'low', debug: {} as any,
    }
  } finally {
    loading.value = false
  }
}

async function loadTrend() {
  if (!selectedMetric.value) return
  loading.value = true
  answer.value = null
  try {
    trendData.value = await getTrends(selectedMetric.value)
    await nextTick()
    renderChart()
  } catch (e: any) {
    trendData.value = null
  } finally {
    loading.value = false
  }
}

function renderChart() {
  if (!chartRef.value || !trendData.value) return
  if (chartInstance) chartInstance.dispose()
  chartInstance = echarts.init(chartRef.value)

  const years = trendData.value.data.map(d => `FY${d.fiscal_year}`)
  const values = trendData.value.data.map(d => d.value)
  const isLarge = Math.max(...values.map(Math.abs)) > 1e9

  chartInstance.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '12%', right: '5%', top: '10%', bottom: '15%' },
    xAxis: { type: 'category', data: years },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: (v: number) => isLarge ? `$${(v / 1e9).toFixed(0)}B` : v.toLocaleString(),
      },
    },
    series: [{
      name: formatMetricName(selectedMetric.value),
      type: 'line',
      data: values,
      smooth: true,
      areaStyle: { opacity: 0.15 },
      lineStyle: { width: 3 },
      itemStyle: { color: '#2563eb' },
    }],
  })
}

function toggleCitation(idx: number) {
  expandedCitation.value = expandedCitation.value === idx ? null : idx
}

function formatMetricName(name: string): string {
  return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function formatValue(val: number, unit: string): string {
  if (unit === 'per_share') return `$${val.toFixed(2)}`
  if (Math.abs(val) >= 1e9) return `$${(val / 1e9).toFixed(1)}B`
  if (Math.abs(val) >= 1e6) return `$${(val / 1e6).toFixed(0)}M`
  return val.toLocaleString()
}

function formatAnswer(text: string): string {
  return text
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
}
</script>

<style>
:root {
  --bg: #f8fafc;
  --sidebar-bg: #ffffff;
  --card-bg: #ffffff;
  --border: #e2e8f0;
  --text: #1e293b;
  --text-secondary: #64748b;
  --primary: #2563eb;
  --primary-light: #dbeafe;
  --success: #16a34a;
  --warning: #d97706;
  --danger: #dc2626;
}

.app { display: flex; flex-direction: column; height: 100vh; background: var(--bg); color: var(--text); }

.header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 24px; background: #0f172a; color: white;
}
.header h1 { font-size: 18px; font-weight: 600; }
.subtitle { font-size: 12px; color: #94a3b8; margin-left: 12px; }
.header-right { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; }
.status-dot.ok { background: var(--success); }
.status-dot.err { background: var(--danger); }

.main { display: flex; flex: 1; overflow: hidden; }

.sidebar {
  width: 300px; min-width: 300px; background: var(--sidebar-bg);
  border-right: 1px solid var(--border); padding: 16px; overflow-y: auto;
}

.section-group { margin-bottom: 20px; }
.section-group h3 { font-size: 13px; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }

.scenario-btn {
  display: flex; align-items: center; gap: 8px; width: 100%; padding: 8px 10px;
  background: none; border: 1px solid transparent; border-radius: 6px;
  font-size: 13px; cursor: pointer; text-align: left; color: var(--text);
}
.scenario-btn:hover { background: var(--primary-light); border-color: var(--primary); }
.scenario-icon { font-size: 16px; }

.metric-select { width: 100%; padding: 8px; border: 1px solid var(--border); border-radius: 6px; font-size: 13px; }

.question-input {
  width: 100%; padding: 8px; border: 1px solid var(--border); border-radius: 6px;
  font-size: 13px; resize: vertical; font-family: inherit;
}
.ask-btn {
  width: 100%; margin-top: 8px; padding: 8px; background: var(--primary);
  color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 500;
}
.ask-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.content { flex: 1; padding: 20px; overflow-y: auto; }

.loading-overlay { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 60px; color: var(--text-secondary); }
.spinner { width: 36px; height: 36px; border: 3px solid var(--border); border-top-color: var(--primary); border-radius: 50%; animation: spin 0.8s linear infinite; margin-bottom: 16px; }
@keyframes spin { to { transform: rotate(360deg); } }

.answer-panel { background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 20px; margin-bottom: 16px; }
.answer-header { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.query-type-badge { padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; text-transform: uppercase; }
.query-type-badge.narrative { background: #dbeafe; color: #1d4ed8; }
.query-type-badge.metric { background: #dcfce7; color: #166534; }
.query-type-badge.comparative { background: #fef3c7; color: #92400e; }
.query-type-badge.report { background: #f3e8ff; color: #6b21a8; }
.confidence-badge { padding: 3px 8px; border-radius: 4px; font-size: 11px; }
.confidence-badge.high { background: #dcfce7; color: #166534; }
.confidence-badge.medium { background: #fef3c7; color: #92400e; }
.confidence-badge.low { background: #fee2e2; color: #991b1b; }
.timing { font-size: 12px; color: var(--text-secondary); margin-left: auto; }
.answer-body { font-size: 14px; line-height: 1.7; }
.answer-body p { margin-bottom: 8px; }

.debug-bar { display: flex; gap: 12px; margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--border); font-size: 11px; color: var(--text-secondary); flex-wrap: wrap; }

.citations-panel { margin-bottom: 16px; }
.citations-panel h3 { font-size: 14px; font-weight: 600; margin-bottom: 8px; }
.citation-card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 6px; margin-bottom: 6px; cursor: pointer; }
.citation-card:hover { border-color: var(--primary); }
.citation-header { display: flex; align-items: center; gap: 8px; padding: 8px 12px; font-size: 12px; }
.citation-badge { background: #0f172a; color: white; padding: 2px 6px; border-radius: 3px; font-weight: 600; font-size: 11px; }
.citation-section { color: var(--text); font-weight: 500; }
.citation-id { color: var(--text-secondary); margin-left: auto; font-family: monospace; font-size: 11px; }
.citation-body { padding: 8px 12px; font-size: 13px; color: var(--text-secondary); line-height: 1.5; border-top: 1px solid var(--border); white-space: pre-wrap; }

.trend-panel { background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 20px; }
.trend-panel h3 { font-size: 15px; margin-bottom: 12px; }
.chart-container { width: 100%; height: 320px; }
.cagr-badge { display: inline-block; margin: 12px 0; padding: 4px 12px; background: var(--primary-light); color: var(--primary); border-radius: 4px; font-size: 13px; font-weight: 600; }

.trend-table { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 12px; }
.trend-table th { text-align: left; padding: 8px; border-bottom: 2px solid var(--border); font-weight: 600; font-size: 12px; color: var(--text-secondary); }
.trend-table td { padding: 8px; border-bottom: 1px solid var(--border); }
.positive { color: var(--success); }
.negative { color: var(--danger); }

.empty-state { text-align: center; padding: 80px 40px; }
.empty-state h2 { font-size: 22px; margin-bottom: 8px; }
.empty-state p { color: var(--text-secondary); margin-bottom: 32px; }
.capabilities { display: flex; gap: 24px; justify-content: center; }
.cap-item { text-align: left; max-width: 200px; }
.cap-item strong { display: block; font-size: 14px; margin-bottom: 4px; }
.cap-item span { font-size: 13px; color: var(--text-secondary); }
</style>
