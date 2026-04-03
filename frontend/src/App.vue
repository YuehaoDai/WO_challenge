<template>
  <div class="app">
    <header class="header">
      <div class="header-left">
        <h1>AAPL 10-K Intelligence</h1>
        <span class="subtitle">{{ t('subtitle') }}</span>
      </div>
      <div class="header-right">
        <button class="lang-toggle" @click="toggleLang">{{ locale === 'en' ? '中文' : 'EN' }}</button>
        <span class="status-dot" :class="systemOk ? 'ok' : 'err'"></span>
        <span class="status-text">{{ systemOk ? t('systemReady') : t('connecting') }}</span>
      </div>
    </header>

    <div class="main">
      <aside class="sidebar">
        <div class="section-group">
          <h3>{{ t('analysisScenarios') }}</h3>
          <button v-for="s in localizedScenarios" :key="s.label" class="scenario-btn" @click="askQuestion(s.question)">
            <span class="scenario-icon">{{ s.icon }}</span>
            <span>{{ s.label }}</span>
          </button>
        </div>

        <div class="section-group">
          <h3>{{ t('financialTrends') }}</h3>
          <select v-model="selectedMetric" @change="loadTrend" class="metric-select">
            <option value="">{{ t('selectMetric') }}</option>
            <option v-for="m in availableMetrics" :key="m" :value="m">{{ formatMetricName(m) }}</option>
          </select>
        </div>

        <div class="section-group">
          <h3>{{ t('customQuestion') }}</h3>
          <textarea v-model="customQuestion" :placeholder="t('questionPlaceholder')" class="question-input" rows="3" @keydown.enter.ctrl="askQuestion(customQuestion)"></textarea>
          <button class="ask-btn" @click="askQuestion(customQuestion)" :disabled="loading || !customQuestion.trim()">
            {{ loading ? t('analyzing') : t('analyze') }}
          </button>
        </div>
      </aside>

      <section class="content">
        <div v-if="loading" class="loading-overlay">
          <div class="spinner"></div>
          <p>{{ t('loadingText') }}</p>
        </div>

        <div v-if="answer" class="answer-panel">
          <div class="answer-header">
            <span class="query-type-badge" :class="answer.query_type">{{ t('queryType_' + answer.query_type) }}</span>
            <span class="confidence-badge" :class="answer.confidence">{{ t('confidence_' + answer.confidence) }}</span>
            <span class="timing">{{ answer.debug?.total_time_ms }}ms</span>
          </div>
          <div class="answer-body" v-html="formatAnswer(answer.answer)"></div>

          <div class="debug-bar" v-if="answer.debug">
            <span>FTS: {{ answer.debug.fts_hits }}</span>
            <span>Dense: {{ answer.debug.dense_hits }}</span>
            <span>RRF: {{ answer.debug.after_rrf }}</span>
            <span>Reranked: {{ answer.debug.after_rerank }}</span>
            <span>{{ t('context') }}: {{ answer.debug.context_chunks }}</span>
            <span>{{ t('retrieval') }}: {{ answer.debug.retrieval_time_ms }}ms</span>
            <span>{{ t('generation') }}: {{ answer.debug.generation_time_ms }}ms</span>
          </div>
        </div>

        <div v-if="answer?.citations?.length" class="citations-panel">
          <h3>{{ t('evidenceSources') }}</h3>
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
              <tr><th>{{ t('fiscalYear') }}</th><th>{{ t('value') }}</th><th>{{ t('yoyChange') }}</th><th>{{ t('yoyPct') }}</th></tr>
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
          <h2>{{ t('emptyTitle') }}</h2>
          <p>{{ t('emptyDesc') }}</p>
          <div class="capabilities">
            <div class="cap-item">
              <strong>{{ t('capNarrative') }}</strong>
              <span>{{ t('capNarrativeDesc') }}</span>
            </div>
            <div class="cap-item">
              <strong>{{ t('capMetrics') }}</strong>
              <span>{{ t('capMetricsDesc') }}</span>
            </div>
            <div class="cap-item">
              <strong>{{ t('capComparison') }}</strong>
              <span>{{ t('capComparisonDesc') }}</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import { ask, getTrends, getSystemStatus, type AskResponse, type TrendsResponse } from './api/client'

type Locale = 'en' | 'zh'
const locale = ref<Locale>((localStorage.getItem('locale') as Locale) || 'en')

function toggleLang() {
  locale.value = locale.value === 'en' ? 'zh' : 'en'
  localStorage.setItem('locale', locale.value)
}

const i18n: Record<Locale, Record<string, string>> = {
  en: {
    subtitle: '2020–2025 SEC Filing Analysis',
    systemReady: 'System Ready',
    connecting: 'Connecting...',
    analysisScenarios: 'Analysis Scenarios',
    financialTrends: 'Financial Trends',
    selectMetric: 'Select metric...',
    customQuestion: 'Custom Question',
    questionPlaceholder: "Ask about Apple's 10-K filings...",
    analyzing: 'Analyzing...',
    analyze: 'Analyze',
    loadingText: 'Retrieving evidence and generating analysis...',
    evidenceSources: 'Evidence Sources',
    context: 'Context',
    retrieval: 'Retrieval',
    generation: 'Generation',
    fiscalYear: 'Fiscal Year',
    value: 'Value',
    yoyChange: 'YoY Change',
    yoyPct: 'YoY %',
    emptyTitle: 'Apple 10-K Filing Intelligence',
    emptyDesc: "Select an analysis scenario or ask a custom question to analyze Apple's SEC 10-K filings from 2020 to 2025.",
    capNarrative: 'Narrative Q&A',
    capNarrativeDesc: 'Business strategy, risk factors, management discussion',
    capMetrics: 'Financial Metrics',
    capMetricsDesc: 'Revenue, margins, EPS with deterministic calculations',
    capComparison: 'Cross-Year Comparison',
    capComparisonDesc: 'Compare risk themes, strategy shifts across years',
    queryType_narrative: 'Narrative',
    queryType_metric: 'Metric',
    queryType_comparative: 'Comparative',
    queryType_report: 'Report',
    queryType_error: 'Error',
    confidence_high: 'High confidence',
    confidence_medium: 'Medium confidence',
    confidence_low: 'Low confidence',
  },
  zh: {
    subtitle: '2020–2025 SEC 年报分析',
    systemReady: '系统就绪',
    connecting: '连接中...',
    analysisScenarios: '分析场景',
    financialTrends: '财务趋势',
    selectMetric: '选择指标...',
    customQuestion: '自定义提问',
    questionPlaceholder: '输入关于 Apple 10-K 年报的问题...',
    analyzing: '分析中...',
    analyze: '开始分析',
    loadingText: '正在检索证据并生成分析...',
    evidenceSources: '证据来源',
    context: '上下文',
    retrieval: '检索耗时',
    generation: '生成耗时',
    fiscalYear: '财年',
    value: '数值',
    yoyChange: '同比变化',
    yoyPct: '同比 %',
    emptyTitle: 'Apple 10-K 年报智能分析',
    emptyDesc: '选择左侧分析场景，或输入自定义问题，分析 Apple 2020–2025 年 SEC 10-K 年报。',
    capNarrative: '叙述型问答',
    capNarrativeDesc: '业务战略、风险因素、管理层讨论',
    capMetrics: '财务指标',
    capMetricsDesc: '营收、利润率、EPS 确定性计算',
    capComparison: '跨年对比',
    capComparisonDesc: '风险主题、战略变化的多年比较',
    queryType_narrative: '叙述型',
    queryType_metric: '数值型',
    queryType_comparative: '比较型',
    queryType_report: '报告',
    queryType_error: '错误',
    confidence_high: '高置信度',
    confidence_medium: '中置信度',
    confidence_low: '低置信度',
  },
}

function t(key: string): string {
  return i18n[locale.value][key] ?? key
}

const scenariosData = {
  en: [
    { icon: '📊', label: 'Business Overview', question: "What are Apple's main business segments and products as described in the most recent 10-K?" },
    { icon: '⚠️', label: 'Key Risk Factors', question: "What are the most significant risk factors Apple disclosed in its 2025 10-K filing?" },
    { icon: '💰', label: 'Revenue Analysis', question: "What was Apple's net sales and how did it change compared to the prior year?" },
    { icon: '📈', label: 'Profitability Trends', question: "Compare Apple's gross margin and operating income trends from 2020 to 2025" },
    { icon: '🌍', label: 'Tariff & Trade Impact', question: "How does Apple describe the impact of tariffs and trade restrictions in recent filings?" },
    { icon: '🔬', label: 'R&D Investment', question: "How has Apple's research and development spending changed from 2020 to 2025?" },
    { icon: '💵', label: 'Capital Return', question: "Summarize Apple's share repurchase and dividend activity across 2020-2025" },
    { icon: '📱', label: 'Product Strategy', question: "How has Apple's product lineup evolved based on the Business section across multiple years?" },
  ],
  zh: [
    { icon: '📊', label: '业务概览', question: "What are Apple's main business segments and products as described in the most recent 10-K?" },
    { icon: '⚠️', label: '关键风险因素', question: "What are the most significant risk factors Apple disclosed in its 2025 10-K filing?" },
    { icon: '💰', label: '营收分析', question: "What was Apple's net sales and how did it change compared to the prior year?" },
    { icon: '📈', label: '盈利趋势', question: "Compare Apple's gross margin and operating income trends from 2020 to 2025" },
    { icon: '🌍', label: '关税与贸易影响', question: "How does Apple describe the impact of tariffs and trade restrictions in recent filings?" },
    { icon: '🔬', label: '研发投入', question: "How has Apple's research and development spending changed from 2020 to 2025?" },
    { icon: '💵', label: '资本回报', question: "Summarize Apple's share repurchase and dividend activity across 2020-2025" },
    { icon: '📱', label: '产品策略', question: "How has Apple's product lineup evolved based on the Business section across multiple years?" },
  ],
}

const localizedScenarios = computed(() => scenariosData[locale.value])

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

const metricNameZh: Record<string, string> = {
  net_sales: '净营收', gross_profit: '毛利润', operating_income: '营业利润',
  net_income: '净利润', eps_diluted: '稀释每股收益', rd_expense: '研发费用',
  total_assets: '总资产', total_liabilities: '总负债', long_term_debt: '长期负债',
  operating_cash_flow: '经营性现金流', share_repurchases: '股票回购',
  cost_of_sales: '销售成本', income_before_tax: '税前利润',
  eps_basic: '基本每股收益', sga_expense: '销售管理费用',
  operating_expenses: '营业费用', total_equity: '股东权益',
  cash_and_equivalents: '现金及等价物', capex: '资本支出', dividends_paid: '已付股息',
}

function formatMetricName(name: string): string {
  if (locale.value === 'zh' && metricNameZh[name]) return metricNameZh[name]
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
.header-right { display: flex; align-items: center; gap: 10px; font-size: 13px; }
.lang-toggle {
  padding: 3px 10px; border: 1px solid #475569; border-radius: 4px;
  background: transparent; color: #cbd5e1; font-size: 12px; font-weight: 500;
  cursor: pointer; transition: all 0.15s;
}
.lang-toggle:hover { background: #1e293b; border-color: #94a3b8; color: white; }
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
