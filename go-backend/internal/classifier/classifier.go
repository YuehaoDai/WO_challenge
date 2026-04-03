package classifier

import (
	"regexp"
	"strings"

	"github.com/WO_challenge/go-backend/internal/dto"
)

// Rule-based query classifier. Fail-closed: defaults to narrative (the most
// thorough retrieval + generation path) when classification is uncertain.

var metricKeywords = []string{
	"revenue", "net sales", "income", "profit", "margin", "eps",
	"earnings per share", "cash", "debt", "asset", "liability",
	"equity", "capex", "dividend", "share repurchase", "buyback",
	"operating cash flow", "free cash flow", "gross margin",
	"operating margin", "net margin", "cagr", "growth rate",
	"how much", "what was the", "what is the",
	"多少", "营收", "利润", "毛利", "净利", "每股", "增长",
}

var comparativeKeywords = []string{
	"compare", "comparison", "vs", "versus", "differ", "difference",
	"change between", "changed from", "year over year", "yoy",
	"对比", "比较", "变化", "相比",
}

var reportKeywords = []string{
	"summarize", "summary", "report", "overview", "analyze", "analysis",
	"brief", "highlight", "key point", "main theme",
	"总结", "分析", "概述", "要点",
}

var yearPattern = regexp.MustCompile(`\b(20[12]\d)\b`)
var trendKeywords = []string{
	"trend", "over time", "past", "years", "from 20", "history",
	"趋势", "历年", "过去",
}

// Classify determines the query type using rule-based matching.
// Returns (queryType, detectedYears, detectedSectionHints).
func Classify(question string) (dto.QueryType, []int, []string) {
	q := strings.ToLower(question)

	years := extractYears(q)
	sectionHints := extractSectionHints(q)

	if matchesAny(q, comparativeKeywords) || (len(years) >= 2) {
		return dto.QueryComparative, years, sectionHints
	}

	if matchesAny(q, reportKeywords) {
		return dto.QueryReport, years, sectionHints
	}

	if matchesAny(q, metricKeywords) {
		if matchesAny(q, trendKeywords) || len(years) >= 2 {
			return dto.QueryComparative, years, sectionHints
		}
		return dto.QueryMetric, years, sectionHints
	}

	return dto.QueryNarrative, years, sectionHints
}

func matchesAny(text string, keywords []string) bool {
	for _, kw := range keywords {
		if strings.Contains(text, kw) {
			return true
		}
	}
	return false
}

func extractYears(text string) []int {
	matches := yearPattern.FindAllString(text, -1)
	seen := map[int]bool{}
	var years []int
	for _, m := range matches {
		y := 0
		for _, c := range m {
			y = y*10 + int(c-'0')
		}
		if y >= 2020 && y <= 2025 && !seen[y] {
			seen[y] = true
			years = append(years, y)
		}
	}
	return years
}

func extractSectionHints(text string) []string {
	q := strings.ToLower(text)
	var hints []string

	sectionMap := map[string]string{
		"business":        "Item 1 Business",
		"risk":            "Item 1A Risk Factors",
		"md&a":            "Item 7",
		"management discussion": "Item 7",
		"financial statement":   "Item 8",
		"balance sheet":   "Balance Sheet",
		"income statement": "Income Statement",
		"cash flow":       "Cash Flow Statement",
		"property":        "Item 2 Properties",
		"legal":           "Item 3 Legal Proceedings",
	}

	for keyword, section := range sectionMap {
		if strings.Contains(q, keyword) {
			hints = append(hints, section)
		}
	}

	return hints
}
