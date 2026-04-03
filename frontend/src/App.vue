<template>
  <div class="app">
    <div class="ambient-glow"></div>

    <aside class="nav-rail">
      <div class="nav-top">
        <div class="nav-logo">
          <span class="logo-icon">◆</span>
        </div>
        <button class="nav-tab" :class="{ active: activeTab === 'chat' }" @click="activeTab = 'chat'" :title="t('chat')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>
          <span>{{ t('chat') }}</span>
        </button>
        <button class="nav-tab" :class="{ active: activeTab === 'report' }" @click="activeTab = 'report'" :title="t('report')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
          <span>{{ t('report') }}</span>
        </button>
      </div>
      <div class="nav-bottom">
        <button class="nav-action" @click="newChat" :title="t('newChat')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        </button>
        <button class="nav-action lang-btn" @click="toggleLang">{{ locale === 'en' ? '中' : 'EN' }}</button>
        <div class="status-indicator" :class="systemOk ? 'ok' : 'err'" :title="systemOk ? t('systemReady') : t('connecting')"></div>
      </div>
    </aside>

    <main class="main-area">
      <!-- ==================== CHAT VIEW ==================== -->
      <div v-if="activeTab === 'chat'" class="chat-view">
        <div class="messages-container" ref="messagesRef">
          <!-- Welcome screen -->
          <div v-if="messages.length === 0 && !loading" class="welcome">
            <div class="welcome-header">
              <h1>AAPL 10-K Intelligence</h1>
              <p class="welcome-sub">{{ t('welcomeDesc') }}</p>
            </div>
            <div class="suggestions-grid">
              <button v-for="s in localizedStarters" :key="s.label" class="suggestion-card" @click="sendMessage(s.question)">
                <span class="suggestion-icon">{{ s.icon }}</span>
                <span class="suggestion-label">{{ s.label }}</span>
                <span class="suggestion-tag">{{ s.tag }}</span>
              </button>
            </div>
          </div>

          <!-- Message list -->
          <template v-for="(msg, idx) in messages" :key="msg.id">
            <div class="msg" :class="msg.role">
              <div v-if="msg.role === 'user'" class="msg-user-bubble">{{ msg.content }}</div>
              <div v-else class="msg-assistant-card glass-card">
                <div class="msg-meta" v-if="msg.queryType">
                  <span class="badge type" :class="msg.queryType">{{ t('qt_' + msg.queryType) }}</span>
                  <span class="badge conf" :class="msg.confidence">{{ t('cf_' + msg.confidence) }}</span>
                  <span class="msg-timing" v-if="msg.debug?.total_time_ms">{{ msg.debug.total_time_ms }}ms</span>
                </div>
                <div class="msg-body markdown-body" v-html="renderMd(msg.content)"></div>

                <!-- Inline ECharts -->
                <div v-if="msg.trendData" class="msg-chart-wrap">
                  <div class="msg-chart" :ref="el => setChartRef(msg.id, el as HTMLElement)"></div>
                  <div v-if="msg.trendData.cagr !== null" class="cagr-pill">CAGR: {{ msg.trendData.cagr }}%</div>
                </div>

                <!-- Citations -->
                <details v-if="msg.citations?.length" class="msg-citations">
                  <summary>{{ t('evidenceSources') }} ({{ msg.citations.length }})</summary>
                  <div v-for="(c, ci) in msg.citations" :key="ci" class="cite-item">
                    <span class="cite-fy">FY{{ c.fiscal_year }}</span>
                    <span class="cite-section">{{ c.section_title }}</span>
                    <p class="cite-text">{{ c.snippet }}</p>
                  </div>
                </details>

                <!-- Debug -->
                <details v-if="msg.debug?.fts_hits !== undefined" class="msg-debug">
                  <summary>Debug</summary>
                  <div class="debug-pills">
                    <span>FTS: {{ msg.debug.fts_hits }}</span>
                    <span>Dense: {{ msg.debug.dense_hits }}</span>
                    <span>RRF: {{ msg.debug.after_rrf }}</span>
                    <span>Rerank: {{ msg.debug.after_rerank }}</span>
                    <span>{{ t('retrieval') }}: {{ msg.debug.retrieval_time_ms }}ms</span>
                    <span>{{ t('generation') }}: {{ msg.debug.generation_time_ms }}ms</span>
                  </div>
                </details>
              </div>
            </div>

            <!-- Follow-up suggestions after last assistant message -->
            <div v-if="msg.role === 'assistant' && idx === messages.length - 1 && !loading" class="followup-chips">
              <button v-for="f in getFollowUps(msg.queryType)" :key="f" class="chip" @click="sendMessage(f)">{{ f }}</button>
            </div>
          </template>

          <!-- Loading indicator -->
          <div v-if="loading" class="msg assistant">
            <div class="msg-assistant-card glass-card loading-card">
              <div class="typing-dots"><span></span><span></span><span></span></div>
              <span class="loading-text">{{ t('analyzing') }}</span>
            </div>
          </div>
        </div>

        <!-- Input bar -->
        <div class="input-bar glass-card">
          <div class="input-row">
            <button class="trend-btn" @click="showTrendPicker = !showTrendPicker" :title="t('trendBtn')">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
            </button>
            <textarea
              ref="inputRef"
              v-model="inputText"
              :placeholder="t('inputPlaceholder')"
              rows="1"
              @keydown="handleKeydown"
              @input="autoResize"
            ></textarea>
            <button class="send-btn" :disabled="!inputText.trim() || loading" @click="sendMessage(inputText)">
              <svg v-if="!loading" viewBox="0 0 24 24" fill="currentColor"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
              <div v-else class="send-spinner"></div>
            </button>
          </div>
          <!-- Trend picker popover -->
          <div v-if="showTrendPicker" class="trend-popover glass-card">
            <button v-for="m in metricsList" :key="m" class="trend-option" @click="insertTrend(m)">{{ fmtMetric(m) }}</button>
          </div>
        </div>
      </div>

      <!-- ==================== REPORT VIEW ==================== -->
      <div v-if="activeTab === 'report'" class="report-view">
        <!-- Template selector -->
        <div v-if="!activeReport" class="report-templates">
          <h2>{{ t('reportTitle') }}</h2>
          <p class="report-subtitle">{{ t('reportDesc') }}</p>
          <div class="template-grid">
            <button v-for="r in localizedReports" :key="r.id" class="template-card glass-card" @click="generateReport(r.id)">
              <span class="template-icon">{{ r.icon }}</span>
              <span class="template-name">{{ r.name }}</span>
              <span class="template-desc">{{ r.desc }}</span>
            </button>
          </div>
        </div>

        <!-- Report content -->
        <div v-else class="report-content">
          <button class="back-btn" @click="activeReport = null">← {{ t('backToTemplates') }}</button>
          <h2 class="report-heading">{{ activeReportTitle }}</h2>

          <!-- Metric cards -->
          <div v-if="reportMetrics.length" class="metric-cards">
            <div v-for="mc in reportMetrics" :key="mc.label" class="metric-card glass-card">
              <span class="mc-value">{{ mc.value }}</span>
              <span class="mc-label">{{ mc.label }}</span>
              <span v-if="mc.change" class="mc-change" :class="mc.change > 0 ? 'up' : 'down'">
                {{ mc.change > 0 ? '+' : '' }}{{ mc.change.toFixed(1) }}%
              </span>
            </div>
          </div>

          <!-- Report charts -->
          <div v-if="reportChartData" class="report-chart-section glass-card">
            <div class="report-chart" ref="reportChartRef"></div>
          </div>

          <!-- Report text -->
          <div v-if="reportText" class="report-text glass-card">
            <div class="markdown-body" v-html="renderMd(reportText)"></div>
          </div>

          <div v-if="reportLoading" class="report-loading">
            <div class="typing-dots"><span></span><span></span><span></span></div>
            <span>{{ t('generatingReport') }}</span>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import { marked } from 'marked'
import { ask, getTrends, getSystemStatus, type AskResponse, type TrendsResponse, type Citation, type HistoryMessage } from './api/client'

marked.setOptions({ breaks: true, gfm: true })

// ─── i18n ────────────────────────────────────────────────────────
type Locale = 'en' | 'zh'
const locale = ref<Locale>((localStorage.getItem('locale') as Locale) || 'en')
function toggleLang() { locale.value = locale.value === 'en' ? 'zh' : 'en'; localStorage.setItem('locale', locale.value) }

const i18n: Record<Locale, Record<string, string>> = {
  en: {
    chat: 'Chat', report: 'Reports', newChat: 'New Chat', systemReady: 'Online', connecting: 'Connecting',
    welcomeDesc: 'Intelligent analysis of Apple SEC 10-K filings, FY2020–2025. Ask anything about business strategy, financials, risks, and trends.',
    inputPlaceholder: 'Ask about Apple\'s 10-K filings...',
    analyzing: 'Analyzing...', evidenceSources: 'Evidence Sources', retrieval: 'Retrieval', generation: 'Generation',
    trendBtn: 'Insert trend chart',
    qt_narrative: 'Narrative', qt_metric: 'Metric', qt_comparative: 'Comparative', qt_report: 'Report', qt_error: 'Error',
    cf_high: 'High', cf_medium: 'Medium', cf_low: 'Low',
    reportTitle: 'Analysis Reports', reportDesc: 'Generate structured reports powered by RAG + financial data.',
    backToTemplates: 'Back', generatingReport: 'Generating report...',
  },
  zh: {
    chat: '对话', report: '报告', newChat: '新对话', systemReady: '在线', connecting: '连接中',
    welcomeDesc: 'Apple SEC 10-K 年报智能分析（FY2020-2025）。业务战略、财务数据、风险因素、趋势分析，尽在掌握。',
    inputPlaceholder: '输入关于 Apple 10-K 年报的问题...',
    analyzing: '分析中...', evidenceSources: '证据来源', retrieval: '检索', generation: '生成',
    trendBtn: '插入趋势图',
    qt_narrative: '叙述型', qt_metric: '数值型', qt_comparative: '比较型', qt_report: '报告', qt_error: '错误',
    cf_high: '高置信', cf_medium: '中置信', cf_low: '低置信',
    reportTitle: '分析报告', reportDesc: '基于 RAG + 结构化金融数据生成专业分析报告。',
    backToTemplates: '返回', generatingReport: '正在生成报告...',
  },
}
function t(k: string) { return i18n[locale.value][k] ?? k }

// ─── Starter suggestions ────────────────────────────────────────
const starters = {
  en: [
    { icon: '🏢', label: 'Products & Business Segments', tag: 'Item 1', question: "What are Apple's main products and business segments as described in the most recent 10-K?" },
    { icon: '⚠️', label: 'Key Risk Factors', tag: 'Item 1A', question: "What are the most significant risk factors Apple disclosed in its 2025 10-K filing?" },
    { icon: '📈', label: 'Revenue Trend FY20-25', tag: 'Item 7', question: "How has Apple's net revenue changed from FY2020 to FY2025?" },
    { icon: '💵', label: 'Diluted EPS FY2025', tag: 'Item 8', question: "What was Apple's diluted EPS in FY2025?" },
    { icon: '🌐', label: 'Tariff & Supply Chain', tag: 'Item 1A', question: "How does Apple describe the impact of tariffs and supply chain risks in recent filings?" },
    { icon: '🔬', label: 'R&D Spending Trends', tag: 'Item 7', question: "Compare Apple's research and development spending trends across the past 6 years" },
  ],
  zh: [
    { icon: '🏢', label: '产品与业务板块', tag: 'Item 1', question: "What are Apple's main products and business segments as described in the most recent 10-K?" },
    { icon: '⚠️', label: '关键风险因素', tag: 'Item 1A', question: "What are the most significant risk factors Apple disclosed in its 2025 10-K filing?" },
    { icon: '📈', label: '营收趋势 FY20-25', tag: 'Item 7', question: "How has Apple's net revenue changed from FY2020 to FY2025?" },
    { icon: '💵', label: '2025 稀释每股收益', tag: 'Item 8', question: "What was Apple's diluted EPS in FY2025?" },
    { icon: '🌐', label: '关税与供应链风险', tag: 'Item 1A', question: "How does Apple describe the impact of tariffs and supply chain risks in recent filings?" },
    { icon: '🔬', label: '研发支出趋势', tag: 'Item 7', question: "Compare Apple's research and development spending trends across the past 6 years" },
  ],
}
const localizedStarters = computed(() => starters[locale.value])

// ─── Follow-up suggestions ──────────────────────────────────────
const followUpsMap: Record<string, { en: string[]; zh: string[] }> = {
  narrative: {
    en: ["What are the related risk factors?", "How has this changed compared to prior years?", "Show the revenue trend chart"],
    zh: ["相关的风险因素有哪些？", "与往年相比有何变化？", "展示营收趋势图"],
  },
  metric: {
    en: ["How does this compare to the prior year?", "What drove this change?", "Show the trend over 6 years"],
    zh: ["与前一年相比如何？", "是什么推动了这一变化？", "展示近六年趋势"],
  },
  comparative: {
    en: ["What are the underlying reasons?", "How do margins compare?", "Summarize the overall financial health"],
    zh: ["背后的原因是什么？", "利润率如何对比？", "总结整体财务健康状况"],
  },
}
function getFollowUps(qt?: string): string[] {
  if (!qt || !followUpsMap[qt]) return followUpsMap.narrative[locale.value]
  return followUpsMap[qt][locale.value]
}

// ─── Report templates ───────────────────────────────────────────
interface ReportTemplate { id: string; icon: string; name: string; desc: string }
const reports: Record<Locale, ReportTemplate[]> = {
  en: [
    { id: 'annual', icon: '📊', name: 'Annual Financial Overview', desc: 'Revenue, net income, EPS trends with narrative summary' },
    { id: 'risk', icon: '⚠️', name: 'Risk Assessment', desc: 'Key risk factors analysis and year-over-year changes' },
    { id: 'profit', icon: '📈', name: 'Profitability Analysis', desc: 'Gross profit, operating income, and margin trends' },
    { id: 'rnd', icon: '🔬', name: 'R&D & Strategy', desc: 'Research investment trends and product strategy evolution' },
    { id: 'brief', icon: '📋', name: 'Investment Research Brief', desc: 'Comprehensive one-page investment thesis' },
  ],
  zh: [
    { id: 'annual', icon: '📊', name: '年度财务总览', desc: '营收、净利润、EPS 趋势及叙述性摘要' },
    { id: 'risk', icon: '⚠️', name: '风险因素评估', desc: '关键风险因素分析及同比变化' },
    { id: 'profit', icon: '📈', name: '盈利能力分析', desc: '毛利润、营业利润、利润率趋势' },
    { id: 'rnd', icon: '🔬', name: '研发与战略', desc: '研发投入趋势及产品战略演变' },
    { id: 'brief', icon: '📋', name: '综合投研简报', desc: '一页式综合投资分析报告' },
  ],
}
const localizedReports = computed(() => reports[locale.value])

// ─── Chat state ─────────────────────────────────────────────────
interface ChatMessage {
  id: string; role: 'user' | 'assistant'; content: string; timestamp: number
  queryType?: string; citations?: Citation[]; debug?: AskResponse['debug']
  confidence?: string; trendData?: TrendsResponse
}

const activeTab = ref<'chat' | 'report'>('chat')
const messages = ref<ChatMessage[]>([])
const inputText = ref('')
const loading = ref(false)
const systemOk = ref(false)
const messagesRef = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLTextAreaElement | null>(null)
const showTrendPicker = ref(false)

const metricsList = ['net_sales', 'gross_profit', 'operating_income', 'net_income', 'eps_diluted', 'rd_expense', 'total_assets', 'operating_cash_flow', 'share_repurchases']

const metricZh: Record<string, string> = {
  net_sales: '净营收', gross_profit: '毛利润', operating_income: '营业利润', net_income: '净利润',
  eps_diluted: '稀释EPS', rd_expense: '研发费用', total_assets: '总资产', operating_cash_flow: '经营现金流',
  share_repurchases: '股票回购', total_liabilities: '总负债', long_term_debt: '长期负债',
  cost_of_sales: '销售成本', total_equity: '股东权益', capex: '资本支出',
}
function fmtMetric(m: string) {
  if (locale.value === 'zh' && metricZh[m]) return metricZh[m]
  return m.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function renderMd(text: string) { return marked.parse(text) as string }
let msgCounter = 0
function uid() { return `msg-${Date.now()}-${msgCounter++}` }

// ─── Chat actions ───────────────────────────────────────────────
onMounted(async () => {
  try { await getSystemStatus(); systemOk.value = true } catch { systemOk.value = false }
})

function buildHistory(): HistoryMessage[] {
  const hist: HistoryMessage[] = []
  const recent = messages.value.slice(-6)
  for (const m of recent) {
    hist.push({ role: m.role, content: m.content })
  }
  return hist
}

async function sendMessage(text: string) {
  const q = text.trim()
  if (!q || loading.value) return
  inputText.value = ''
  showTrendPicker.value = false
  resetInputHeight()

  messages.value.push({ id: uid(), role: 'user', content: q, timestamp: Date.now() })
  scrollToBottom()
  loading.value = true

  try {
    const history = buildHistory().slice(0, -1)
    const resp = await ask({ question: q, lang: locale.value, history })
    const assistantMsg: ChatMessage = {
      id: uid(), role: 'assistant', content: resp.answer, timestamp: Date.now(),
      queryType: resp.query_type, citations: resp.citations, debug: resp.debug, confidence: resp.confidence,
    }

    if (resp.query_type === 'metric' || resp.query_type === 'comparative') {
      const metric = detectMetric(q)
      if (metric) {
        try {
          const td = await getTrends(metric)
          assistantMsg.trendData = td
        } catch { /* trend is optional */ }
      }
    }

    messages.value.push(assistantMsg)
  } catch (e: any) {
    messages.value.push({
      id: uid(), role: 'assistant', content: `Error: ${e.message || 'Request failed'}`, timestamp: Date.now(),
      queryType: 'error', confidence: 'low',
    })
  } finally {
    loading.value = false
    await nextTick()
    scrollToBottom()
    renderAllCharts()
  }
}

function newChat() { messages.value = []; inputText.value = '' }

async function insertTrend(metric: string) {
  showTrendPicker.value = false
  loading.value = true
  messages.value.push({ id: uid(), role: 'user', content: `📈 ${fmtMetric(metric)} Trend`, timestamp: Date.now() })
  scrollToBottom()
  try {
    const td = await getTrends(metric)
    const lines = td.data.map(d => `FY${d.fiscal_year}: ${fmtVal(d.value, td.unit)}${d.yoy_pct != null ? ` (${d.yoy_pct > 0 ? '+' : ''}${d.yoy_pct.toFixed(1)}%)` : ''}`)
    const text = `### ${fmtMetric(metric)} — AAPL FY2020–2025\n\n${lines.join('\n')}\n\n${td.cagr != null ? `**CAGR: ${td.cagr}%**` : ''}`
    messages.value.push({ id: uid(), role: 'assistant', content: text, timestamp: Date.now(), trendData: td, queryType: 'metric', confidence: 'high' })
  } catch (e: any) {
    messages.value.push({ id: uid(), role: 'assistant', content: `Failed to load trend: ${e.message}`, timestamp: Date.now(), queryType: 'error', confidence: 'low' })
  } finally {
    loading.value = false
    await nextTick()
    scrollToBottom()
    renderAllCharts()
  }
}

function detectMetric(question: string): string | null {
  const q = question.toLowerCase()
  const map: [string[], string][] = [
    [['revenue', 'net sales', 'sales', '营收', '净营收'], 'net_sales'],
    [['net income', 'profit', '净利润', '利润'], 'net_income'],
    [['eps', 'earnings per share', '每股收益'], 'eps_diluted'],
    [['gross margin', 'gross profit', '毛利'], 'gross_profit'],
    [['operating income', 'operating profit', '营业利润'], 'operating_income'],
    [['r&d', 'research', '研发'], 'rd_expense'],
    [['total assets', '总资产'], 'total_assets'],
    [['cash flow', '现金流'], 'operating_cash_flow'],
    [['repurchase', 'buyback', '回购'], 'share_repurchases'],
  ]
  for (const [keywords, metric] of map) {
    if (keywords.some(kw => q.includes(kw))) return metric
  }
  return null
}

function fmtVal(val: number, unit: string) {
  if (unit === 'per_share') return `$${val.toFixed(2)}`
  if (Math.abs(val) >= 1e9) return `$${(val / 1e9).toFixed(1)}B`
  if (Math.abs(val) >= 1e6) return `$${(val / 1e6).toFixed(0)}M`
  return val.toLocaleString()
}

// ─── Input handling ─────────────────────────────────────────────
function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage(inputText.value)
  }
}
function autoResize() {
  const el = inputRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
}
function resetInputHeight() { if (inputRef.value) inputRef.value.style.height = 'auto' }
function scrollToBottom() { nextTick(() => { if (messagesRef.value) messagesRef.value.scrollTop = messagesRef.value.scrollHeight }) }

// ─── ECharts ────────────────────────────────────────────────────
const chartRefs = new Map<string, HTMLElement>()
const chartInstances = new Map<string, echarts.ECharts>()

function setChartRef(id: string, el: HTMLElement | null) {
  if (el) chartRefs.set(id, el)
}

function renderAllCharts() {
  for (const msg of messages.value) {
    if (!msg.trendData) continue
    const el = chartRefs.get(msg.id)
    if (!el) continue
    if (chartInstances.has(msg.id)) chartInstances.get(msg.id)!.dispose()
    const chart = echarts.init(el)
    chartInstances.set(msg.id, chart)
    const td = msg.trendData
    const years = td.data.map(d => `FY${d.fiscal_year}`)
    const values = td.data.map(d => d.value)
    const isLarge = Math.max(...values.map(Math.abs)) > 1e9
    chart.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis', backgroundColor: 'rgba(15,23,42,0.9)', borderColor: '#334155', textStyle: { color: '#f1f5f9' } },
      grid: { left: '12%', right: '5%', top: '8%', bottom: '12%' },
      xAxis: { type: 'category', data: years, axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#94a3b8' } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: '#1e293b' } }, axisLabel: { color: '#94a3b8', formatter: (v: number) => isLarge ? `$${(v / 1e9).toFixed(0)}B` : v.toLocaleString() } },
      series: [{ type: 'line', data: values, smooth: true, areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(59,130,246,0.3)' }, { offset: 1, color: 'rgba(59,130,246,0)' }]) }, lineStyle: { width: 2.5, color: '#3b82f6' }, itemStyle: { color: '#3b82f6' }, symbol: 'circle', symbolSize: 6 }],
    })
  }
}

watch(messages, () => { nextTick(() => renderAllCharts()) }, { deep: true })

// ─── Report system ──────────────────────────────────────────────
const activeReport = ref<string | null>(null)
const reportLoading = ref(false)
const reportText = ref('')
const reportMetrics = ref<{ label: string; value: string; change?: number }[]>([])
const reportChartData = ref<TrendsResponse[] | null>(null)
const reportChartRef = ref<HTMLElement | null>(null)
let reportChartInstance: echarts.ECharts | null = null

const activeReportTitle = computed(() => {
  const r = localizedReports.value.find(r => r.id === activeReport.value)
  return r ? `${r.icon} ${r.name}` : ''
})

const reportConfigs: Record<string, { metrics: string[]; question: string; questionZh: string }> = {
  annual: {
    metrics: ['net_sales', 'net_income', 'eps_diluted'],
    question: "Provide a comprehensive overview of Apple's financial performance from FY2020 to FY2025, covering revenue growth, profitability, and key highlights.",
    questionZh: "Provide a comprehensive overview of Apple's financial performance from FY2020 to FY2025, covering revenue growth, profitability, and key highlights.",
  },
  risk: {
    metrics: [],
    question: "What are the most significant risk factors Apple disclosed in its recent 10-K filings, and how have they evolved from FY2020 to FY2025?",
    questionZh: "What are the most significant risk factors Apple disclosed in its recent 10-K filings, and how have they evolved from FY2020 to FY2025?",
  },
  profit: {
    metrics: ['gross_profit', 'operating_income', 'net_income'],
    question: "Analyze Apple's profitability trends from FY2020 to FY2025, including gross margin, operating margin changes and the underlying drivers.",
    questionZh: "Analyze Apple's profitability trends from FY2020 to FY2025, including gross margin, operating margin changes and the underlying drivers.",
  },
  rnd: {
    metrics: ['rd_expense'],
    question: "How has Apple's R&D spending evolved from FY2020 to FY2025, and what does the 10-K reveal about their product strategy and innovation focus?",
    questionZh: "How has Apple's R&D spending evolved from FY2020 to FY2025, and what does the 10-K reveal about their product strategy and innovation focus?",
  },
  brief: {
    metrics: ['net_sales', 'net_income', 'eps_diluted', 'operating_cash_flow'],
    question: "Create a concise investment research brief for Apple (AAPL) covering: business overview, financial highlights (FY2020-2025), key risks, competitive positioning, and growth outlook based on the 10-K filings.",
    questionZh: "Create a concise investment research brief for Apple (AAPL) covering: business overview, financial highlights (FY2020-2025), key risks, competitive positioning, and growth outlook based on the 10-K filings.",
  },
}

async function generateReport(id: string) {
  activeReport.value = id
  reportLoading.value = true
  reportText.value = ''
  reportMetrics.value = []
  reportChartData.value = null
  const cfg = reportConfigs[id]
  if (!cfg) return

  try {
    const trendPromises = cfg.metrics.map(m => getTrends(m).catch(() => null))
    const trends = await Promise.all(trendPromises)
    const validTrends = trends.filter(Boolean) as TrendsResponse[]
    reportChartData.value = validTrends.length ? validTrends : null

    reportMetrics.value = validTrends.map(td => {
      const latest = td.data[td.data.length - 1]
      const prev = td.data.length >= 2 ? td.data[td.data.length - 2] : null
      return {
        label: fmtMetric(td.metric),
        value: fmtVal(latest.value, td.unit),
        change: prev ? ((latest.value - prev.value) / Math.abs(prev.value)) * 100 : undefined,
      }
    })

    await nextTick()
    renderReportChart()

    const question = cfg.question
    const resp = await ask({ question, lang: locale.value })
    reportText.value = resp.answer
  } catch (e: any) {
    reportText.value = `Error generating report: ${e.message}`
  } finally {
    reportLoading.value = false
  }
}

function renderReportChart() {
  if (!reportChartRef.value || !reportChartData.value?.length) return
  if (reportChartInstance) reportChartInstance.dispose()
  reportChartInstance = echarts.init(reportChartRef.value)
  const colors = ['#3b82f6', '#06b6d4', '#8b5cf6', '#f59e0b']
  const allData = reportChartData.value
  const years = allData[0].data.map(d => `FY${d.fiscal_year}`)

  reportChartInstance.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(15,23,42,0.9)', borderColor: '#334155', textStyle: { color: '#f1f5f9' } },
    legend: { data: allData.map(d => fmtMetric(d.metric)), textStyle: { color: '#94a3b8' }, top: 0 },
    grid: { left: '10%', right: '5%', top: '14%', bottom: '10%' },
    xAxis: { type: 'category', data: years, axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#94a3b8' } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#1e293b' } }, axisLabel: { color: '#94a3b8', formatter: (v: number) => Math.abs(v) >= 1e9 ? `$${(v / 1e9).toFixed(0)}B` : v.toLocaleString() } },
    series: allData.map((td, i) => ({
      name: fmtMetric(td.metric),
      type: 'line',
      data: td.data.map(d => d.value),
      smooth: true,
      lineStyle: { width: 2.5, color: colors[i % colors.length] },
      itemStyle: { color: colors[i % colors.length] },
      symbol: 'circle',
      symbolSize: 5,
    })),
  })
}

watch(reportChartData, () => { nextTick(() => renderReportChart()) })
</script>

<style>
*,*::before,*::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Roboto, sans-serif; }

:root {
  --bg-base: #0a0f1a;
  --bg-surface: rgba(255,255,255,0.03);
  --bg-elevated: rgba(255,255,255,0.06);
  --glass-border: rgba(255,255,255,0.08);
  --glass-blur: 20px;
  --text-primary: #f1f5f9;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  --accent: #3b82f6;
  --accent-cyan: #06b6d4;
  --accent-gradient: linear-gradient(135deg, #3b82f6, #06b6d4);
  --success: #22c55e;
  --danger: #ef4444;
  --warning: #f59e0b;
  --nav-width: 68px;
}

.app { display: flex; height: 100vh; background: var(--bg-base); color: var(--text-primary); overflow: hidden; position: relative; }
.ambient-glow { position: fixed; top: -200px; left: 50%; width: 800px; height: 400px; background: radial-gradient(ellipse, rgba(59,130,246,0.08) 0%, transparent 70%); transform: translateX(-50%); pointer-events: none; z-index: 0; }

.glass-card {
  background: var(--bg-surface);
  border: 1px solid var(--glass-border);
  border-radius: 12px;
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
}

/* ─── Nav Rail ─────────────────────────────────── */
.nav-rail {
  width: var(--nav-width); min-width: var(--nav-width);
  display: flex; flex-direction: column; justify-content: space-between; align-items: center;
  padding: 16px 0; background: rgba(15,23,42,0.6);
  border-right: 1px solid var(--glass-border); z-index: 10;
}
.nav-top, .nav-bottom { display: flex; flex-direction: column; align-items: center; gap: 8px; }
.nav-logo { font-size: 20px; color: var(--accent); margin-bottom: 16px; }
.logo-icon { display: inline-block; background: var(--accent-gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 800; font-size: 24px; }

.nav-tab {
  display: flex; flex-direction: column; align-items: center; gap: 3px;
  width: 52px; padding: 8px 0; border: none; border-radius: 10px;
  background: transparent; color: var(--text-muted); cursor: pointer;
  font-size: 10px; transition: all 0.2s;
}
.nav-tab svg { width: 22px; height: 22px; }
.nav-tab:hover { color: var(--text-secondary); background: var(--bg-elevated); }
.nav-tab.active { color: var(--accent); background: rgba(59,130,246,0.12); }

.nav-action {
  width: 38px; height: 38px; border-radius: 10px; border: 1px solid var(--glass-border);
  background: transparent; color: var(--text-muted); cursor: pointer;
  display: flex; align-items: center; justify-content: center; transition: all 0.2s;
}
.nav-action svg { width: 18px; height: 18px; }
.nav-action:hover { color: var(--text-primary); background: var(--bg-elevated); border-color: var(--accent); }
.lang-btn { font-size: 12px; font-weight: 600; }
.status-indicator { width: 10px; height: 10px; border-radius: 50%; margin-top: 4px; }
.status-indicator.ok { background: var(--success); box-shadow: 0 0 8px rgba(34,197,94,0.5); }
.status-indicator.err { background: var(--danger); box-shadow: 0 0 8px rgba(239,68,68,0.5); }

/* ─── Main Area ────────────────────────────────── */
.main-area { flex: 1; display: flex; flex-direction: column; overflow: hidden; z-index: 1; }

/* ─── Chat View ────────────────────────────────── */
.chat-view { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

.messages-container {
  flex: 1; overflow-y: auto; padding: 24px; display: flex; flex-direction: column; gap: 16px;
  scrollbar-width: thin; scrollbar-color: #334155 transparent;
}

/* Welcome */
.welcome { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 40px; }
.welcome-header { text-align: center; margin-bottom: 40px; }
.welcome-header h1 { font-size: 32px; font-weight: 700; background: var(--accent-gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 10px; }
.welcome-sub { color: var(--text-secondary); font-size: 15px; max-width: 500px; line-height: 1.6; }

.suggestions-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; max-width: 720px; width: 100%; }
@media (max-width: 800px) { .suggestions-grid { grid-template-columns: repeat(2, 1fr); } }

.suggestion-card {
  display: flex; flex-direction: column; gap: 6px; padding: 16px; border-radius: 12px;
  background: var(--bg-surface); border: 1px solid var(--glass-border);
  cursor: pointer; text-align: left; color: var(--text-primary); transition: all 0.2s;
}
.suggestion-card:hover { border-color: var(--accent); box-shadow: 0 0 24px rgba(59,130,246,0.1); transform: translateY(-1px); }
.suggestion-icon { font-size: 20px; }
.suggestion-label { font-size: 13px; font-weight: 600; }
.suggestion-tag { font-size: 11px; color: var(--text-muted); }

/* Messages */
.msg { display: flex; max-width: 800px; width: 100%; margin: 0 auto; }
.msg.user { justify-content: flex-end; }
.msg.assistant { justify-content: flex-start; }

.msg-user-bubble {
  max-width: 70%; padding: 12px 18px; border-radius: 18px 18px 4px 18px;
  background: var(--accent-gradient); color: white; font-size: 14px; line-height: 1.6; word-break: break-word;
}

.msg-assistant-card {
  max-width: 85%; padding: 16px 20px; border-radius: 4px 16px 16px 16px;
}
.msg-assistant-card:hover { border-color: rgba(59,130,246,0.2); }

.msg-meta { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
.badge { padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; }
.badge.type { background: rgba(59,130,246,0.15); color: #60a5fa; }
.badge.type.metric { background: rgba(34,197,94,0.15); color: #4ade80; }
.badge.type.comparative { background: rgba(245,158,11,0.15); color: #fbbf24; }
.badge.conf { background: rgba(255,255,255,0.06); color: var(--text-secondary); }
.msg-timing { font-size: 11px; color: var(--text-muted); margin-left: auto; }

/* Markdown body */
.markdown-body { font-size: 14px; line-height: 1.75; color: var(--text-primary); }
.markdown-body p { margin-bottom: 10px; }
.markdown-body h1,.markdown-body h2,.markdown-body h3,.markdown-body h4 { margin: 16px 0 8px; font-weight: 600; color: var(--text-primary); }
.markdown-body h2 { font-size: 17px; } .markdown-body h3 { font-size: 15px; }
.markdown-body ul,.markdown-body ol { padding-left: 20px; margin-bottom: 10px; }
.markdown-body li { margin-bottom: 4px; }
.markdown-body strong { color: #e2e8f0; }
.markdown-body table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 13px; }
.markdown-body th,.markdown-body td { padding: 8px 12px; border: 1px solid #1e293b; text-align: left; }
.markdown-body th { background: rgba(255,255,255,0.04); font-weight: 600; }
.markdown-body code { background: rgba(255,255,255,0.06); padding: 2px 6px; border-radius: 4px; font-size: 13px; color: #e2e8f0; }
.markdown-body pre { background: rgba(0,0,0,0.3); padding: 14px; border-radius: 8px; overflow-x: auto; margin: 12px 0; border: 1px solid #1e293b; }
.markdown-body pre code { background: none; padding: 0; }
.markdown-body blockquote { border-left: 3px solid var(--accent); padding-left: 14px; margin: 12px 0; color: var(--text-secondary); }

/* Inline chart */
.msg-chart-wrap { margin-top: 12px; }
.msg-chart { width: 100%; height: 240px; }
.cagr-pill { display: inline-block; margin-top: 8px; padding: 3px 10px; border-radius: 6px; font-size: 12px; font-weight: 600; background: rgba(59,130,246,0.12); color: #60a5fa; }

/* Citations & debug (collapsible) */
.msg-citations, .msg-debug { margin-top: 10px; }
.msg-citations summary, .msg-debug summary {
  font-size: 12px; color: var(--text-muted); cursor: pointer; padding: 4px 0; user-select: none;
}
.msg-citations summary:hover, .msg-debug summary:hover { color: var(--text-secondary); }
.cite-item { padding: 8px 10px; border-left: 2px solid #334155; margin: 6px 0 6px 4px; }
.cite-fy { font-size: 11px; font-weight: 700; color: var(--accent); margin-right: 8px; }
.cite-section { font-size: 12px; color: var(--text-secondary); }
.cite-text { font-size: 12px; color: var(--text-muted); margin-top: 4px; line-height: 1.4; }
.debug-pills { display: flex; gap: 10px; flex-wrap: wrap; font-size: 11px; color: var(--text-muted); padding: 6px 0; }

/* Follow-up chips */
.followup-chips { display: flex; gap: 8px; flex-wrap: wrap; max-width: 800px; width: 100%; margin: 0 auto; padding-left: 0; }
.chip {
  padding: 6px 14px; border-radius: 20px; font-size: 12px;
  background: var(--bg-surface); border: 1px solid var(--glass-border);
  color: var(--text-secondary); cursor: pointer; transition: all 0.2s; white-space: nowrap;
}
.chip:hover { border-color: var(--accent); color: var(--accent); background: rgba(59,130,246,0.06); }

/* Loading */
.loading-card { display: flex; align-items: center; gap: 12px; padding: 16px 20px; }
.loading-text { font-size: 13px; color: var(--text-muted); }
.typing-dots { display: flex; gap: 4px; }
.typing-dots span { width: 6px; height: 6px; border-radius: 50%; background: var(--accent); animation: blink 1.4s infinite both; }
.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink { 0%,80%,100% { opacity: 0.2; } 40% { opacity: 1; } }

/* ─── Input Bar ────────────────────────────────── */
.input-bar { margin: 0 24px 20px; padding: 10px 14px; position: relative; }
.input-row { display: flex; align-items: flex-end; gap: 10px; }

.input-bar textarea {
  flex: 1; background: transparent; border: none; outline: none; resize: none;
  color: var(--text-primary); font-size: 14px; font-family: inherit; line-height: 1.5;
  max-height: 120px; padding: 4px 0;
}
.input-bar textarea::placeholder { color: var(--text-muted); }

.trend-btn, .send-btn {
  width: 36px; height: 36px; border-radius: 10px; border: none; cursor: pointer;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0; transition: all 0.2s;
}
.trend-btn { background: transparent; color: var(--text-muted); }
.trend-btn svg { width: 18px; height: 18px; }
.trend-btn:hover { color: var(--accent); background: rgba(59,130,246,0.1); }

.send-btn { background: var(--accent-gradient); color: white; }
.send-btn svg { width: 18px; height: 18px; }
.send-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.send-btn:not(:disabled):hover { box-shadow: 0 0 16px rgba(59,130,246,0.4); }

.send-spinner { width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.3); border-top-color: white; border-radius: 50%; animation: spin 0.7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.trend-popover {
  position: absolute; bottom: 100%; left: 14px; margin-bottom: 8px; padding: 8px;
  display: flex; flex-wrap: wrap; gap: 6px; max-width: 400px; z-index: 20;
}
.trend-option {
  padding: 5px 12px; border-radius: 8px; font-size: 12px; border: 1px solid var(--glass-border);
  background: var(--bg-elevated); color: var(--text-secondary); cursor: pointer; transition: all 0.15s;
}
.trend-option:hover { border-color: var(--accent); color: var(--accent); }

/* ─── Report View ──────────────────────────────── */
.report-view { flex: 1; overflow-y: auto; padding: 32px; scrollbar-width: thin; scrollbar-color: #334155 transparent; }

.report-templates { max-width: 780px; margin: 0 auto; }
.report-templates h2 { font-size: 26px; font-weight: 700; background: var(--accent-gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 8px; }
.report-subtitle { color: var(--text-secondary); font-size: 14px; margin-bottom: 28px; }

.template-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 14px; }

.template-card {
  display: flex; flex-direction: column; gap: 8px; padding: 20px; cursor: pointer; transition: all 0.2s;
}
.template-card:hover { border-color: var(--accent); box-shadow: 0 0 24px rgba(59,130,246,0.1); transform: translateY(-2px); }
.template-icon { font-size: 28px; }
.template-name { font-size: 15px; font-weight: 600; }
.template-desc { font-size: 12px; color: var(--text-muted); line-height: 1.4; }

.report-content { max-width: 850px; margin: 0 auto; }
.back-btn {
  background: none; border: none; color: var(--text-muted); font-size: 13px;
  cursor: pointer; margin-bottom: 16px; padding: 4px 0;
}
.back-btn:hover { color: var(--accent); }
.report-heading { font-size: 24px; font-weight: 700; margin-bottom: 20px; }

.metric-cards { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 20px; }
.metric-card { padding: 16px 20px; min-width: 150px; flex: 1; text-align: center; }
.mc-value { display: block; font-size: 22px; font-weight: 700; color: var(--text-primary); }
.mc-label { display: block; font-size: 12px; color: var(--text-muted); margin-top: 4px; }
.mc-change { display: block; font-size: 12px; margin-top: 4px; font-weight: 600; }
.mc-change.up { color: var(--success); }
.mc-change.down { color: var(--danger); }

.report-chart-section { padding: 20px; margin-bottom: 20px; }
.report-chart { width: 100%; height: 340px; }

.report-text { padding: 24px; margin-bottom: 20px; }

.report-loading { display: flex; align-items: center; gap: 12px; padding: 24px; color: var(--text-muted); }
</style>
