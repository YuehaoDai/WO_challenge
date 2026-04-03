<template>
  <div class="app">
    <div class="ambient-glow"></div>

    <aside class="nav-rail">
      <div class="nav-top">
        <div class="nav-logo" title="William O'Neil + Co.">
          <img class="logo-icon" src="./assets/logo.jpeg" alt="William O'Neil + Co." />
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
      <!-- ==================== WARM-UP BANNER ==================== -->
      <Transition name="banner-slide">
        <div v-if="systemOk && !modelsReady" class="warmup-banner">
          <div class="warmup-icon">
            <svg class="spinner" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>
          </div>
          <div class="warmup-text">
            <strong>{{ t('warmupTitle') }}</strong>
            <span>{{ t('warmupDetail') }}</span>
          </div>
          <div class="warmup-chips">
            <span class="warmup-chip" :class="embeddingReady ? 'ready' : 'loading'">
              {{ t('warmupEmbedding') }}: {{ embeddingReady ? t('warmupReady') : t('warmupLoading') }}
            </span>
            <span class="warmup-chip" :class="rerankerReady ? 'ready' : 'loading'">
              {{ t('warmupReranker') }}: {{ rerankerReady ? t('warmupReady') : t('warmupLoading') }}
            </span>
          </div>
        </div>
      </Transition>

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
        <!-- Step 1: Template selector -->
        <div v-if="reportStep === 'select'" class="report-templates">
          <h2>{{ t('reportTitle') }}</h2>
          <p class="report-subtitle">{{ t('reportDesc') }}</p>
          <div class="template-grid">
            <button v-for="r in localizedReports" :key="r.id" class="template-card glass-card" @click="selectReport(r.id)">
              <span class="template-icon">{{ r.icon }}</span>
              <span class="template-name">{{ r.name }}</span>
              <span class="template-desc">{{ r.desc }}</span>
            </button>
          </div>
        </div>

        <!-- Step 2: Parameter configuration -->
        <div v-if="reportStep === 'config'" class="report-config">
          <button class="back-btn" @click="reportStep = 'select'">← {{ t('backToTemplates') }}</button>
          <h2 class="config-heading">{{ activeReportTitle }}</h2>
          <p class="config-desc">{{ t('configDesc') }}</p>

          <div class="param-form glass-card">
            <div v-for="param in currentParams" :key="param.key" class="param-group">
              <label class="param-label">{{ param.label[locale] }}</label>

              <div v-if="param.type === 'yearRange'" class="param-year-range">
                <select v-model="paramValues[param.key + '_start']" class="param-select">
                  <option v-for="y in yearOptions" :key="y" :value="y">FY{{ y }}</option>
                </select>
                <span class="range-sep">—</span>
                <select v-model="paramValues[param.key + '_end']" class="param-select">
                  <option v-for="y in yearOptions" :key="y" :value="y">FY{{ y }}</option>
                </select>
              </div>

              <select v-if="param.type === 'select'" v-model="paramValues[param.key]" class="param-select">
                <option v-for="opt in param.options" :key="opt.value" :value="opt.value">{{ opt.label[locale] }}</option>
              </select>

              <div v-if="param.type === 'multiselect'" class="param-chips">
                <label v-for="opt in param.options" :key="opt.value" class="param-chip"
                  :class="{ active: (paramValues[param.key] as string[])?.includes(opt.value) }">
                  <input type="checkbox" :value="opt.value"
                    @change="toggleMulti(param.key, opt.value)" hidden />
                  {{ opt.label[locale] }}
                </label>
              </div>

              <div v-if="param.type === 'radio'" class="param-radios">
                <label v-for="opt in param.options" :key="opt.value" class="param-radio"
                  :class="{ active: paramValues[param.key] === opt.value }">
                  <input type="radio" :name="param.key" :value="opt.value"
                    v-model="paramValues[param.key]" hidden />
                  {{ opt.label[locale] }}
                </label>
              </div>
            </div>

            <button class="generate-btn" @click="runReport">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="18" height="18"><polygon points="5 3 19 12 5 21 5 3"/></svg>
              {{ t('generateBtn') }}
            </button>
          </div>
        </div>

        <!-- Step 3: Report content -->
        <div v-if="reportStep === 'result'" class="report-content">
          <div class="report-toolbar">
            <button class="back-btn" @click="reportStep = 'config'">← {{ t('backToConfig') }}</button>
            <button v-if="!reportLoading && reportText" class="download-btn" @click="downloadReportPdf">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="16" height="16"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              {{ t('downloadPdf') }}
            </button>
          </div>

          <div class="report-body" ref="reportBodyRef">
            <h2 class="report-heading">{{ activeReportTitle }}</h2>
            <p class="report-date">AAPL · SEC 10-K · FY{{ paramValues.year_start || 2020 }}–{{ paramValues.year_end || 2025 }} · {{ new Date().toLocaleDateString() }}</p>

            <div v-if="reportMetrics.length" class="metric-cards">
              <div v-for="mc in reportMetrics" :key="mc.label" class="metric-card glass-card">
                <span class="mc-value">{{ mc.value }}</span>
                <span class="mc-label">{{ mc.label }}</span>
                <span v-if="mc.change" class="mc-change" :class="mc.change > 0 ? 'up' : 'down'">
                  {{ mc.change > 0 ? '+' : '' }}{{ mc.change.toFixed(1) }}%
                </span>
              </div>
            </div>

            <div v-if="reportText" class="report-section">
              <div class="markdown-body" v-html="renderMd(reportText)"></div>
            </div>

            <div v-if="reportChartData" class="report-section">
              <h3 class="section-heading">{{ t('trendChart') }}</h3>
              <div class="report-chart-wrap glass-card">
                <div class="report-chart" ref="reportChartRef"></div>
              </div>
            </div>

            <div v-if="reportChartData" class="report-section">
              <h3 class="section-heading">{{ t('trendTable') }}</h3>
              <div class="report-table-wrap glass-card">
                <table class="trend-table">
                  <thead>
                    <tr>
                      <th>{{ t('fiscalYear') }}</th>
                      <th v-for="td in reportChartData" :key="td.metric">{{ fmtMetric(td.metric) }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(_, yi) in reportChartData[0].data" :key="yi">
                      <td>FY{{ reportChartData[0].data[yi].fiscal_year }}</td>
                      <td v-for="td in reportChartData" :key="td.metric + yi">
                        {{ fmtVal(td.data[yi].value, td.unit) }}
                        <span v-if="td.data[yi].yoy_pct != null" class="table-pct" :class="td.data[yi].yoy_pct! > 0 ? 'up' : 'down'">
                          {{ td.data[yi].yoy_pct! > 0 ? '+' : '' }}{{ td.data[yi].yoy_pct!.toFixed(1) }}%
                        </span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div v-if="reportLoading" class="report-loading">
              <div class="typing-dots"><span></span><span></span><span></span></div>
              <span>{{ t('generatingReport') }}</span>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import { marked } from 'marked'
import jsPDF from 'jspdf'
import html2canvas from 'html2canvas'
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
    backToTemplates: 'Back', backToConfig: 'Parameters', generatingReport: 'Generating report...',
    downloadPdf: 'Download PDF', trendChart: 'Financial Trends', trendTable: 'Detailed Data', fiscalYear: 'Fiscal Year',
    configDesc: 'Configure report parameters below, then generate.',
    generateBtn: 'Generate Report', exportingPdf: 'Exporting PDF...',
    warmupTitle: 'Models loading',
    warmupDetail: 'Some features may be limited while ML models are initializing.',
    warmupEmbedding: 'Embedding', warmupReranker: 'Reranker',
    warmupReady: 'ready', warmupLoading: 'loading',
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
    backToTemplates: '返回', backToConfig: '参数设置', generatingReport: '正在生成报告...',
    downloadPdf: '下载 PDF', trendChart: '财务趋势', trendTable: '详细数据', fiscalYear: '财政年度',
    configDesc: '请在下方配置报告参数，然后点击生成。',
    generateBtn: '生成报告', exportingPdf: '正在导出 PDF...',
    warmupTitle: '模型加载中',
    warmupDetail: 'ML 模型正在初始化，部分功能暂时受限。',
    warmupEmbedding: '向量化模型', warmupReranker: '重排序模型',
    warmupReady: '就绪', warmupLoading: '加载中',
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
const modelsReady = ref(true)
const embeddingReady = ref(true)
const rerankerReady = ref(true)
let warmupPollTimer: ReturnType<typeof setInterval> | null = null
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
async function pollSystemStatus() {
  try {
    const status = await getSystemStatus()
    systemOk.value = true
    modelsReady.value = status.models_ready
    embeddingReady.value = status.embedding_ready
    rerankerReady.value = status.reranker_ready
    if (status.models_ready && warmupPollTimer) {
      clearInterval(warmupPollTimer)
      warmupPollTimer = null
    }
  } catch {
    systemOk.value = false
    modelsReady.value = false
    embeddingReady.value = false
    rerankerReady.value = false
  }
}

onMounted(async () => {
  await pollSystemStatus()
  if (!modelsReady.value) {
    warmupPollTimer = setInterval(pollSystemStatus, 5000)
  }
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
      tooltip: { trigger: 'axis', backgroundColor: '#fff', borderColor: '#e2e8f0', textStyle: { color: '#1e293b' } },
      grid: { left: '12%', right: '5%', top: '8%', bottom: '12%' },
      xAxis: { type: 'category', data: years, axisLine: { lineStyle: { color: '#cbd5e1' } }, axisLabel: { color: '#64748b' } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: '#f1f5f9' } }, axisLabel: { color: '#64748b', formatter: (v: number) => isLarge ? `$${(v / 1e9).toFixed(0)}B` : v.toLocaleString() } },
      series: [{ type: 'line', data: values, smooth: true, areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(37,99,235,0.2)' }, { offset: 1, color: 'rgba(37,99,235,0)' }]) }, lineStyle: { width: 2.5, color: '#2563eb' }, itemStyle: { color: '#2563eb' }, symbol: 'circle', symbolSize: 6 }],
    })
  }
}

watch(messages, () => { nextTick(() => renderAllCharts()) }, { deep: true })

// ─── Report system ──────────────────────────────────────────────
type ReportStep = 'select' | 'config' | 'result'
const reportStep = ref<ReportStep>('select')
const activeReport = ref<string | null>(null)
const reportLoading = ref(false)
const reportText = ref('')
const reportMetrics = ref<{ label: string; value: string; change?: number }[]>([])
const reportChartData = ref<TrendsResponse[] | null>(null)
const reportChartRef = ref<HTMLElement | null>(null)
const reportBodyRef = ref<HTMLElement | null>(null)
let reportChartInstance: echarts.ECharts | null = null

const yearOptions = [2020, 2021, 2022, 2023, 2024, 2025]

const activeReportTitle = computed(() => {
  const r = localizedReports.value.find(r => r.id === activeReport.value)
  return r ? `${r.icon} ${r.name}` : ''
})

// ─── Parameter definitions ──────────────────────────────────────
interface ParamOption { value: string; label: Record<Locale, string> }
interface ParamDef {
  key: string
  type: 'yearRange' | 'select' | 'multiselect' | 'radio'
  label: Record<Locale, string>
  options?: ParamOption[]
  default: any
}

const metricOptions: ParamOption[] = [
  { value: 'net_sales', label: { en: 'Net Revenue', zh: '净营收' } },
  { value: 'gross_profit', label: { en: 'Gross Profit', zh: '毛利润' } },
  { value: 'operating_income', label: { en: 'Operating Income', zh: '营业利润' } },
  { value: 'net_income', label: { en: 'Net Income', zh: '净利润' } },
  { value: 'eps_diluted', label: { en: 'Diluted EPS', zh: '稀释EPS' } },
  { value: 'rd_expense', label: { en: 'R&D Expense', zh: '研发费用' } },
  { value: 'total_assets', label: { en: 'Total Assets', zh: '总资产' } },
  { value: 'operating_cash_flow', label: { en: 'Operating Cash Flow', zh: '经营现金流' } },
  { value: 'share_repurchases', label: { en: 'Share Repurchases', zh: '股票回购' } },
  { value: 'capex', label: { en: 'Capital Expenditure', zh: '资本支出' } },
  { value: 'long_term_debt', label: { en: 'Long-term Debt', zh: '长期负债' } },
  { value: 'total_equity', label: { en: "Stockholders' Equity", zh: '股东权益' } },
]

const reportParamDefs: Record<string, ParamDef[]> = {
  annual: [
    { key: 'year', type: 'yearRange', label: { en: 'Fiscal Year Range', zh: '财政年度范围' }, default: null },
    { key: 'focus_metrics', type: 'multiselect', label: { en: 'Focus Metrics', zh: '关注指标' },
      options: metricOptions.filter(m => ['net_sales','net_income','eps_diluted','operating_cash_flow','total_assets'].includes(m.value)),
      default: ['net_sales', 'net_income', 'eps_diluted'] },
    { key: 'depth', type: 'radio', label: { en: 'Analysis Depth', zh: '分析深度' },
      options: [
        { value: 'summary', label: { en: 'Executive Summary', zh: '摘要版' } },
        { value: 'detailed', label: { en: 'Detailed Analysis', zh: '详细分析' } },
      ], default: 'detailed' },
  ],
  risk: [
    { key: 'year', type: 'yearRange', label: { en: 'Fiscal Year Range', zh: '财政年度范围' }, default: null },
    { key: 'risk_categories', type: 'multiselect', label: { en: 'Risk Categories', zh: '风险类别' },
      options: [
        { value: 'market', label: { en: 'Market & Competition', zh: '市场与竞争' } },
        { value: 'regulatory', label: { en: 'Regulatory & Legal', zh: '监管与法律' } },
        { value: 'supply_chain', label: { en: 'Supply Chain & Manufacturing', zh: '供应链与制造' } },
        { value: 'macro', label: { en: 'Macroeconomic & FX', zh: '宏观经济与汇率' } },
        { value: 'tech', label: { en: 'Technology & Cybersecurity', zh: '技术与网络安全' } },
        { value: 'geopolitical', label: { en: 'Geopolitical & Tariffs', zh: '地缘政治与关税' } },
      ], default: ['market', 'regulatory', 'supply_chain'] },
    { key: 'evolution', type: 'radio', label: { en: 'Include YoY Evolution', zh: '包含同比演变分析' },
      options: [
        { value: 'yes', label: { en: 'Yes — compare across years', zh: '是 — 跨年对比' } },
        { value: 'no', label: { en: 'No — latest year only', zh: '否 — 仅最新年度' } },
      ], default: 'yes' },
  ],
  profit: [
    { key: 'year', type: 'yearRange', label: { en: 'Fiscal Year Range', zh: '财政年度范围' }, default: null },
    { key: 'margin_metrics', type: 'multiselect', label: { en: 'Profitability Metrics', zh: '盈利指标' },
      options: [
        { value: 'gross_profit', label: { en: 'Gross Profit', zh: '毛利润' } },
        { value: 'operating_income', label: { en: 'Operating Income', zh: '营业利润' } },
        { value: 'net_income', label: { en: 'Net Income', zh: '净利润' } },
        { value: 'cost_of_sales', label: { en: 'Cost of Sales', zh: '销售成本' } },
        { value: 'rd_expense', label: { en: 'R&D Expense', zh: '研发费用' } },
        { value: 'net_sales', label: { en: 'Net Revenue (for margin calc)', zh: '净营收（用于利润率计算）' } },
      ],
      default: ['gross_profit', 'operating_income', 'net_income'] },
    { key: 'include_drivers', type: 'radio', label: { en: 'Include Driver Analysis', zh: '包含驱动因素分析' },
      options: [
        { value: 'yes', label: { en: 'Yes — explain margin shifts', zh: '是 — 解释利润率变化原因' } },
        { value: 'no', label: { en: 'No — numbers only', zh: '否 — 仅数据' } },
      ], default: 'yes' },
  ],
  rnd: [
    { key: 'year', type: 'yearRange', label: { en: 'Fiscal Year Range', zh: '财政年度范围' }, default: null },
    { key: 'comparison', type: 'multiselect', label: { en: 'Compare R&D With', zh: 'R&D 对比指标' },
      options: [
        { value: 'net_sales', label: { en: 'Net Revenue (R&D Intensity)', zh: '净营收（研发强度）' } },
        { value: 'operating_income', label: { en: 'Operating Income', zh: '营业利润' } },
        { value: 'capex', label: { en: 'Capital Expenditure', zh: '资本支出' } },
      ], default: ['net_sales'] },
    { key: 'strategy_focus', type: 'radio', label: { en: 'Strategy Focus', zh: '战略重点' },
      options: [
        { value: 'product', label: { en: 'Product Innovation', zh: '产品创新' } },
        { value: 'platform', label: { en: 'Platform & Services', zh: '平台与服务' } },
        { value: 'both', label: { en: 'Both', zh: '两者兼顾' } },
      ], default: 'both' },
  ],
  brief: [
    { key: 'year', type: 'yearRange', label: { en: 'Fiscal Year Range', zh: '财政年度范围' }, default: null },
    { key: 'framework', type: 'radio', label: { en: 'Analysis Framework', zh: '分析框架' },
      options: [
        { value: 'canslim', label: { en: "CAN SLIM (William O'Neil)", zh: "CAN SLIM（威廉·奥尼尔）" } },
        { value: 'fundamental', label: { en: 'Fundamental Analysis', zh: '基本面分析' } },
        { value: 'comprehensive', label: { en: 'Comprehensive', zh: '综合分析' } },
      ], default: 'canslim' },
    { key: 'focus_areas', type: 'multiselect', label: { en: 'Focus Areas', zh: '关注领域' },
      options: [
        { value: 'earnings', label: { en: 'Earnings Growth & Quality', zh: '盈利增长与质量' } },
        { value: 'revenue', label: { en: 'Revenue Momentum', zh: '营收动能' } },
        { value: 'cash_flow', label: { en: 'Cash Flow & Capital Allocation', zh: '现金流与资本配置' } },
        { value: 'competitive', label: { en: 'Competitive Positioning', zh: '竞争定位' } },
        { value: 'risks', label: { en: 'Key Risks', zh: '主要风险' } },
        { value: 'outlook', label: { en: 'Growth Outlook', zh: '增长前景' } },
      ], default: ['earnings', 'revenue', 'cash_flow', 'competitive'] },
    { key: 'depth', type: 'radio', label: { en: 'Report Length', zh: '报告篇幅' },
      options: [
        { value: 'brief', label: { en: 'One-page Brief', zh: '一页简报' } },
        { value: 'detailed', label: { en: 'Detailed Report', zh: '详细报告' } },
      ], default: 'detailed' },
  ],
}

const paramValues = reactive<Record<string, any>>({
  year_start: 2020,
  year_end: 2025,
})

const currentParams = computed<ParamDef[]>(() => {
  if (!activeReport.value) return []
  return reportParamDefs[activeReport.value] || []
})

function selectReport(id: string) {
  activeReport.value = id
  const defs = reportParamDefs[id] || []
  paramValues.year_start = 2020
  paramValues.year_end = 2025
  for (const d of defs) {
    if (d.type === 'yearRange') continue
    paramValues[d.key] = Array.isArray(d.default) ? [...d.default] : d.default
  }
  reportStep.value = 'config'
}

function toggleMulti(key: string, value: string) {
  const arr = paramValues[key] as string[]
  const idx = arr.indexOf(value)
  if (idx >= 0) arr.splice(idx, 1)
  else arr.push(value)
}

// ─── Prompt builders per report type ────────────────────────────
function buildReportPrompt(): { question: string; metrics: string[] } {
  const id = activeReport.value!
  const ys = paramValues.year_start
  const ye = paramValues.year_end

  switch (id) {
    case 'annual': {
      const focusNames = (paramValues.focus_metrics as string[]).map(m => fmtMetric(m)).join(', ')
      const depth = paramValues.depth === 'summary' ? 'concise executive summary (300-400 words)' : 'detailed analysis (800-1200 words)'
      return {
        metrics: paramValues.focus_metrics as string[],
        question: `Provide a ${depth} of Apple Inc.'s (AAPL) financial performance from FY${ys} to FY${ye} based on SEC 10-K filings. Focus on these key metrics: ${focusNames}. Cover: 1) Revenue and growth trajectory, 2) Profitability trends, 3) Key highlights and inflection points, 4) Year-over-year changes and CAGR where applicable. Use specific figures from the filings.`,
      }
    }
    case 'risk': {
      const categories = (paramValues.risk_categories as string[]).map(c => {
        const opt = reportParamDefs.risk[1].options?.find(o => o.value === c)
        return opt ? opt.label.en : c
      }).join(', ')
      const evolution = paramValues.evolution === 'yes'
        ? `Compare how these risks have evolved across FY${ys} to FY${ye}, noting new risks that appeared or risks that were removed.`
        : `Focus on the most recent fiscal year (FY${ye}) 10-K filing.`
      return {
        metrics: ['net_sales', 'operating_income'],
        question: `Analyze Apple's (AAPL) risk factors as disclosed in Item 1A of the 10-K filings (FY${ys}–FY${ye}). Focus on these categories: ${categories}. ${evolution} For each risk category: 1) Summarize the key risks disclosed, 2) Assess severity and likelihood, 3) Note any mitigating factors Apple mentions. Provide specific quotes or references from the filings where relevant.`,
      }
    }
    case 'profit': {
      const marginNames = (paramValues.margin_metrics as string[]).map(m => fmtMetric(m)).join(', ')
      const drivers = paramValues.include_drivers === 'yes'
        ? 'For each margin shift, explain the underlying drivers (product mix, cost structure, pricing, R&D allocation, etc.) citing specific 10-K disclosures from Item 7 MD&A.'
        : ''
      return {
        metrics: paramValues.margin_metrics as string[],
        question: `Analyze Apple's (AAPL) profitability from FY${ys} to FY${ye} based on 10-K filings. Key metrics: ${marginNames}. Cover: 1) Gross margin evolution and cost structure, 2) Operating margin trends, 3) Net margin and bottom-line performance, 4) Segment-level profitability insights if available. ${drivers} Calculate margin percentages where data is available.`,
      }
    }
    case 'rnd': {
      const compMetrics = (paramValues.comparison as string[]).map(m => fmtMetric(m)).join(', ')
      const strategy = paramValues.strategy_focus === 'product' ? 'product innovation and hardware/software integration'
        : paramValues.strategy_focus === 'platform' ? 'platform ecosystem and services growth'
        : 'both product innovation and platform/services strategy'
      return {
        metrics: ['rd_expense', ...(paramValues.comparison as string[])],
        question: `Analyze Apple's (AAPL) R&D spending and innovation strategy from FY${ys} to FY${ye}. Compare R&D expense against: ${compMetrics}. Focus on ${strategy}. Cover: 1) R&D spending trend and growth rate, 2) R&D as percentage of revenue (R&D intensity), 3) What the 10-K MD&A sections reveal about strategic priorities, 4) How R&D investment correlates with product launches and revenue growth. Use specific figures from Item 7 and Item 8.`,
      }
    }
    case 'brief': {
      const framework = paramValues.framework
      const areas = (paramValues.focus_areas as string[]).map(a => {
        const opt = reportParamDefs.brief[2].options?.find(o => o.value === a)
        return opt ? opt.label.en : a
      }).join(', ')
      const length = paramValues.depth === 'brief' ? 'concise one-page brief (500 words max)' : 'detailed investment report (1000-1500 words)'
      let frameworkInstr = ''
      if (framework === 'canslim') {
        frameworkInstr = "Structure the analysis using William O'Neil's CAN SLIM framework: C (Current quarterly earnings), A (Annual earnings growth), N (New products/management/highs), S (Supply and demand), L (Leader or laggard), I (Institutional sponsorship), M (Market direction). Apply each factor to AAPL's 10-K data."
      } else if (framework === 'fundamental') {
        frameworkInstr = 'Use fundamental analysis structure: Business Quality, Financial Health, Valuation Context, Growth Drivers, Risk Assessment.'
      } else {
        frameworkInstr = "Combine fundamental analysis with William O'Neil's CAN SLIM lens where applicable."
      }
      return {
        metrics: ['net_sales', 'net_income', 'eps_diluted', 'operating_cash_flow'],
        question: `Create a ${length} for Apple Inc. (AAPL) based on 10-K filings from FY${ys} to FY${ye}. ${frameworkInstr} Focus areas: ${areas}. Include: specific financial figures, growth rates, and CAGR calculations. End with a clear investment thesis summary. Cite specific 10-K sections.`,
      }
    }
    default:
      return { metrics: ['net_sales'], question: `Analyze Apple's 10-K filings from FY${ys} to FY${ye}.` }
  }
}

async function runReport() {
  reportStep.value = 'result'
  reportLoading.value = true
  reportText.value = ''
  reportMetrics.value = []
  reportChartData.value = null

  const { question, metrics } = buildReportPrompt()

  try {
    const ys = paramValues.year_start as number
    const ye = paramValues.year_end as number
    const [trends, resp] = await Promise.all([
      Promise.all(metrics.map(m => getTrends(m, ys, ye).catch(() => null))),
      ask({ question, lang: locale.value }),
    ])

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

    reportText.value = resp.answer
    await nextTick()
    renderReportChart()
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
  const colors = ['#2563eb', '#0891b2', '#7c3aed', '#d97706']
  const allData = reportChartData.value
  const years = allData[0].data.map(d => `FY${d.fiscal_year}`)

  reportChartInstance.setOption({
    backgroundColor: '#ffffff',
    tooltip: { trigger: 'axis', backgroundColor: '#fff', borderColor: '#e2e8f0', textStyle: { color: '#1e293b' } },
    legend: { data: allData.map(d => fmtMetric(d.metric)), textStyle: { color: '#475569' }, top: 0 },
    grid: { left: '10%', right: '5%', top: '14%', bottom: '10%' },
    xAxis: { type: 'category', data: years, axisLine: { lineStyle: { color: '#cbd5e1' } }, axisLabel: { color: '#64748b' } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#f1f5f9' } }, axisLabel: { color: '#64748b', formatter: (v: number) => Math.abs(v) >= 1e9 ? `$${(v / 1e9).toFixed(0)}B` : v.toLocaleString() } },
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

// ─── PDF export ─────────────────────────────────────────────────
const pdfExporting = ref(false)

async function downloadReportPdf() {
  if (!reportBodyRef.value || pdfExporting.value) return
  pdfExporting.value = true

  try {
    const el = reportBodyRef.value
    const canvas = await html2canvas(el, {
      scale: 2,
      useCORS: true,
      backgroundColor: '#ffffff',
      logging: false,
      windowWidth: el.scrollWidth,
    })

    const pxW = canvas.width
    const pxH = canvas.height

    const pageW = 210
    const margin = 12
    const contentW = pageW - margin * 2
    const scaledH = (pxH * contentW) / pxW

    const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' })
    const pageH = 297
    const usableH = pageH - margin * 2

    const totalPages = Math.ceil(scaledH / usableH)

    for (let page = 0; page < totalPages; page++) {
      if (page > 0) pdf.addPage()

      const srcY = (page * usableH * pxH) / scaledH
      const srcH = Math.min((usableH * pxH) / scaledH, pxH - srcY)
      const destH = (srcH * contentW) / pxW

      const sliceCanvas = document.createElement('canvas')
      sliceCanvas.width = pxW
      sliceCanvas.height = Math.ceil(srcH)
      const ctx = sliceCanvas.getContext('2d')!
      ctx.fillStyle = '#ffffff'
      ctx.fillRect(0, 0, sliceCanvas.width, sliceCanvas.height)
      ctx.drawImage(canvas, 0, srcY, pxW, srcH, 0, 0, pxW, srcH)

      const sliceData = sliceCanvas.toDataURL('image/png')
      pdf.addImage(sliceData, 'PNG', margin, margin, contentW, destH)
    }

    const filename = `AAPL_${activeReport.value}_FY${paramValues.year_start}-${paramValues.year_end}_${new Date().toISOString().slice(0, 10)}.pdf`
    pdf.save(filename)
  } catch (e: any) {
    console.error('PDF export failed:', e)
  } finally {
    pdfExporting.value = false
  }
}
</script>

<style>
*,*::before,*::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Roboto, sans-serif; background: #f5f7fa; color: #1e293b; }
button, input, textarea, select { color: inherit; font: inherit; }

:root {
  --bg-base: #f5f7fa;
  --bg-surface: #ffffff;
  --bg-elevated: #f0f2f5;
  --glass-border: #e2e8f0;
  --glass-blur: 20px;
  --text-primary: #1e293b;
  --text-secondary: #475569;
  --text-muted: #64748b;
  --accent: #2563eb;
  --accent-cyan: #0891b2;
  --accent-gradient: linear-gradient(135deg, #2563eb, #0891b2);
  --success: #16a34a;
  --danger: #dc2626;
  --warning: #d97706;
  --nav-width: 68px;
}

.app { display: flex; height: 100vh; background: var(--bg-base); color: var(--text-primary); overflow: hidden; position: relative; }
.ambient-glow { position: fixed; top: -180px; left: 50%; width: 800px; height: 350px; background: radial-gradient(ellipse, rgba(37,99,235,0.06) 0%, transparent 70%); transform: translateX(-50%); pointer-events: none; z-index: 0; }

.glass-card {
  background: var(--bg-surface);
  border: 1px solid var(--glass-border);
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

/* ─── Warm-up Banner ──────────────────────────────── */
.warmup-banner {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 20px;
  background: linear-gradient(90deg, #fef3c7, #fde68a);
  border-bottom: 1px solid #f59e0b;
  color: #92400e;
  font-size: 13px;
  flex-shrink: 0;
  z-index: 20;
}
.warmup-icon { display: flex; align-items: center; }
.warmup-icon .spinner {
  width: 20px; height: 20px; color: #d97706;
  animation: warmup-spin 1.5s linear infinite;
}
@keyframes warmup-spin { to { transform: rotate(360deg); } }
.warmup-text { display: flex; flex-direction: column; gap: 1px; }
.warmup-text strong { font-size: 13px; color: #78350f; }
.warmup-text span { font-size: 12px; color: #92400e; }
.warmup-chips { display: flex; gap: 8px; margin-left: auto; }
.warmup-chip {
  padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 600;
  white-space: nowrap;
}
.warmup-chip.ready { background: #dcfce7; color: #166534; }
.warmup-chip.loading { background: #fef9c3; color: #854d0e; animation: warmup-pulse 1.5s ease-in-out infinite; }
@keyframes warmup-pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.6; } }

.banner-slide-enter-active, .banner-slide-leave-active { transition: all 0.4s ease; }
.banner-slide-enter-from, .banner-slide-leave-to { opacity: 0; max-height: 0; padding-top: 0; padding-bottom: 0; overflow: hidden; }
.banner-slide-enter-to, .banner-slide-leave-from { opacity: 1; max-height: 60px; }

/* ─── Nav Rail ─────────────────────────────────── */
.nav-rail {
  width: var(--nav-width); min-width: var(--nav-width);
  display: flex; flex-direction: column; justify-content: space-between; align-items: center;
  padding: 16px 0; background: #ffffff;
  border-right: 1px solid var(--glass-border); z-index: 10;
}
.nav-top, .nav-bottom { display: flex; flex-direction: column; align-items: center; gap: 8px; }
.nav-logo { margin-bottom: 16px; cursor: default; }
.logo-icon { display: block; width: 40px; height: 40px; border-radius: 8px; object-fit: cover; }

.nav-tab {
  display: flex; flex-direction: column; align-items: center; gap: 3px;
  width: 52px; padding: 8px 0; border: none; border-radius: 10px;
  background: transparent; color: var(--text-muted); cursor: pointer;
  font-size: 10px; transition: all 0.2s;
}
.nav-tab svg { width: 22px; height: 22px; }
.nav-tab:hover { color: var(--text-primary); background: var(--bg-elevated); }
.nav-tab.active { color: var(--accent); background: #eff6ff; }

.nav-action {
  width: 38px; height: 38px; border-radius: 10px; border: 1px solid var(--glass-border);
  background: transparent; color: var(--text-muted); cursor: pointer;
  display: flex; align-items: center; justify-content: center; transition: all 0.2s;
}
.nav-action svg { width: 18px; height: 18px; }
.nav-action:hover { color: var(--text-primary); background: var(--bg-elevated); border-color: var(--accent); }
.lang-btn { font-size: 12px; font-weight: 600; }
.status-indicator { width: 10px; height: 10px; border-radius: 50%; margin-top: 4px; }
.status-indicator.ok { background: var(--success); box-shadow: 0 0 6px rgba(22,163,74,0.4); }
.status-indicator.err { background: var(--danger); box-shadow: 0 0 6px rgba(220,38,38,0.4); }

/* ─── Main Area ────────────────────────────────── */
.main-area { flex: 1; display: flex; flex-direction: column; overflow: hidden; z-index: 1; }

/* ─── Chat View ────────────────────────────────── */
.chat-view { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

.messages-container {
  flex: 1; overflow-y: auto; padding: 24px; display: flex; flex-direction: column; gap: 16px;
  scrollbar-width: thin; scrollbar-color: #cbd5e1 transparent;
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
.suggestion-card:hover { border-color: var(--accent); box-shadow: 0 2px 12px rgba(37,99,235,0.1); transform: translateY(-1px); }
.suggestion-icon { font-size: 20px; }
.suggestion-label { font-size: 13px; font-weight: 600; color: var(--text-primary); }
.suggestion-tag { font-size: 11px; color: var(--text-secondary); }

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
.msg-assistant-card:hover { border-color: #bfdbfe; }

.msg-meta { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
.badge { padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; }
.badge.type { background: #dbeafe; color: #1d4ed8; }
.badge.type.metric { background: #dcfce7; color: #166534; }
.badge.type.comparative { background: #fef3c7; color: #92400e; }
.badge.conf { background: #f1f5f9; color: var(--text-secondary); }
.msg-timing { font-size: 11px; color: var(--text-muted); margin-left: auto; }

/* Markdown body */
.markdown-body { font-size: 14px; line-height: 1.75; color: var(--text-primary); }
.markdown-body p { margin-bottom: 10px; }
.markdown-body h1,.markdown-body h2,.markdown-body h3,.markdown-body h4 { margin: 16px 0 8px; font-weight: 600; color: #0f172a; }
.markdown-body h2 { font-size: 17px; } .markdown-body h3 { font-size: 15px; }
.markdown-body ul,.markdown-body ol { padding-left: 20px; margin-bottom: 10px; }
.markdown-body li { margin-bottom: 4px; color: #334155; }
.markdown-body strong { color: #0f172a; }
.markdown-body table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 13px; }
.markdown-body th,.markdown-body td { padding: 8px 12px; border: 1px solid #e2e8f0; text-align: left; color: #334155; }
.markdown-body th { background: #f8fafc; font-weight: 600; color: #1e293b; }
.markdown-body code { background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 13px; color: #0f172a; }
.markdown-body pre { background: #f8fafc; padding: 14px; border-radius: 8px; overflow-x: auto; margin: 12px 0; border: 1px solid #e2e8f0; }
.markdown-body pre code { background: none; padding: 0; }
.markdown-body blockquote { border-left: 3px solid var(--accent); padding-left: 14px; margin: 12px 0; color: var(--text-secondary); }

/* Inline chart */
.msg-chart-wrap { margin-top: 12px; }
.msg-chart { width: 100%; height: 240px; }
.cagr-pill { display: inline-block; margin-top: 8px; padding: 3px 10px; border-radius: 6px; font-size: 12px; font-weight: 600; background: #dbeafe; color: #1d4ed8; }

/* Citations & debug (collapsible) */
.msg-citations, .msg-debug { margin-top: 10px; }
.msg-citations summary, .msg-debug summary {
  font-size: 12px; color: var(--text-muted); cursor: pointer; padding: 4px 0; user-select: none;
}
.msg-citations summary:hover, .msg-debug summary:hover { color: var(--text-secondary); }
.cite-item { padding: 8px 10px; border-left: 2px solid #cbd5e1; margin: 6px 0 6px 4px; }
.cite-fy { font-size: 11px; font-weight: 700; color: var(--accent); margin-right: 8px; }
.cite-section { font-size: 12px; color: var(--text-secondary); }
.cite-text { font-size: 12px; color: var(--text-muted); margin-top: 4px; line-height: 1.4; }
.debug-pills { display: flex; gap: 10px; flex-wrap: wrap; font-size: 11px; color: var(--text-muted); padding: 6px 0; }

/* Follow-up chips */
.followup-chips { display: flex; gap: 8px; flex-wrap: wrap; max-width: 800px; width: 100%; margin: 0 auto; padding-left: 0; }
.chip {
  padding: 6px 14px; border-radius: 20px; font-size: 12px;
  background: var(--bg-surface); border: 1px solid var(--glass-border);
  color: var(--text-primary); cursor: pointer; transition: all 0.2s; white-space: nowrap;
}
.chip:hover { border-color: var(--accent); color: var(--accent); background: #eff6ff; }

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
.trend-btn:hover { color: var(--accent); background: #eff6ff; }

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
.report-view { flex: 1; overflow-y: auto; padding: 32px; scrollbar-width: thin; scrollbar-color: #cbd5e1 transparent; }

.report-templates { max-width: 780px; margin: 0 auto; }
.report-templates h2 { font-size: 26px; font-weight: 700; background: var(--accent-gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 8px; }
.report-subtitle { color: var(--text-secondary); font-size: 14px; margin-bottom: 28px; }

.template-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 14px; }

.template-card {
  display: flex; flex-direction: column; gap: 8px; padding: 20px; cursor: pointer; transition: all 0.2s;
}
.template-card:hover { border-color: var(--accent); box-shadow: 0 2px 12px rgba(37,99,235,0.1); transform: translateY(-2px); }
.template-icon { font-size: 28px; }
.template-name { font-size: 15px; font-weight: 600; color: var(--text-primary); }
.template-desc { font-size: 12px; color: var(--text-secondary); line-height: 1.4; }

.report-content { max-width: 850px; margin: 0 auto; }
.report-config { max-width: 700px; margin: 0 auto; }

.config-heading { font-size: 22px; font-weight: 700; margin: 8px 0 4px; }
.config-desc { font-size: 14px; color: var(--text-secondary); margin-bottom: 20px; }

.param-form { padding: 24px; display: flex; flex-direction: column; gap: 20px; }

.param-group { display: flex; flex-direction: column; gap: 8px; }
.param-label { font-size: 13px; font-weight: 600; color: var(--text-primary); }

.param-year-range { display: flex; align-items: center; gap: 10px; }
.range-sep { color: var(--text-muted); }
.param-select {
  padding: 8px 12px; border-radius: 8px; border: 1px solid var(--glass-border);
  background: var(--bg-base); color: var(--text-primary); font-size: 14px; cursor: pointer;
}
.param-select:focus { border-color: var(--accent); outline: none; }

.param-chips, .param-radios { display: flex; flex-wrap: wrap; gap: 8px; }
.param-chip, .param-radio {
  padding: 6px 14px; border-radius: 8px; font-size: 13px; cursor: pointer;
  border: 1px solid var(--glass-border); background: var(--bg-base);
  color: var(--text-secondary); transition: all 0.2s; user-select: none;
}
.param-chip:hover, .param-radio:hover { border-color: var(--accent); color: var(--accent); }
.param-chip.active, .param-radio.active {
  background: #eff6ff; border-color: var(--accent); color: var(--accent); font-weight: 600;
}

.generate-btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  padding: 12px 28px; border-radius: 10px; border: none;
  background: var(--accent-gradient); color: #fff; font-size: 15px; font-weight: 600;
  cursor: pointer; transition: all 0.2s; margin-top: 8px; align-self: flex-start;
}
.generate-btn:hover { box-shadow: 0 4px 16px rgba(37,99,235,0.35); transform: translateY(-1px); }

.report-toolbar {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;
}
.back-btn {
  background: none; border: none; color: var(--text-muted); font-size: 13px;
  cursor: pointer; padding: 6px 0;
}
.back-btn:hover { color: var(--accent); }

.download-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 8px 18px; border-radius: 8px; border: 1px solid var(--accent);
  background: transparent; color: var(--accent); font-size: 13px; font-weight: 600;
  cursor: pointer; transition: all 0.2s;
}
.download-btn:hover { background: var(--accent); color: #fff; box-shadow: 0 2px 10px rgba(37,99,235,0.25); }

.report-body { background: #fff; padding: 32px; border-radius: 12px; border: 1px solid var(--glass-border); }
.report-heading { font-size: 24px; font-weight: 700; margin-bottom: 4px; }
.report-date { font-size: 13px; color: var(--text-muted); margin-bottom: 20px; }

.metric-cards { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 24px; }
.metric-card { padding: 16px 20px; min-width: 150px; flex: 1; text-align: center; }
.mc-value { display: block; font-size: 22px; font-weight: 700; color: var(--text-primary); }
.mc-label { display: block; font-size: 12px; color: var(--text-muted); margin-top: 4px; }
.mc-change { display: block; font-size: 12px; margin-top: 4px; font-weight: 600; }
.mc-change.up { color: var(--success); }
.mc-change.down { color: var(--danger); }

.report-section { margin-bottom: 24px; }
.section-heading { font-size: 17px; font-weight: 600; color: var(--text-primary); margin-bottom: 12px; padding-left: 10px; border-left: 3px solid var(--accent); }

.report-chart-wrap { padding: 20px; }
.report-chart { width: 100%; height: 340px; }

.report-table-wrap { padding: 0; overflow-x: auto; }
.trend-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.trend-table th, .trend-table td { padding: 10px 14px; border-bottom: 1px solid #e2e8f0; text-align: left; }
.trend-table th { background: #f8fafc; font-weight: 600; color: #1e293b; font-size: 12px; text-transform: uppercase; letter-spacing: 0.03em; }
.trend-table tbody tr:hover { background: #f8fafc; }
.trend-table td { color: #334155; }
.table-pct { font-size: 11px; font-weight: 600; margin-left: 6px; }
.table-pct.up { color: var(--success); }
.table-pct.down { color: var(--danger); }

.report-loading { display: flex; align-items: center; gap: 12px; padding: 24px; color: var(--text-muted); }
</style>
