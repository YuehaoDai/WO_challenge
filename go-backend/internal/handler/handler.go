package handler

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"

	"github.com/WO_challenge/go-backend/internal/dto"
	"github.com/WO_challenge/go-backend/internal/modelclient"
	"github.com/WO_challenge/go-backend/internal/retrieval"
	"github.com/WO_challenge/go-backend/internal/service"
)

type Handler struct {
	askService *service.AskService
	client     *modelclient.Client
	fts        *retrieval.FTSSearcher
	logger     *zap.Logger
}

func New(askService *service.AskService, client *modelclient.Client, fts *retrieval.FTSSearcher, logger *zap.Logger) *Handler {
	return &Handler{
		askService: askService,
		client:     client,
		fts:        fts,
		logger:     logger,
	}
}

func (h *Handler) Ask(c *gin.Context) {
	var req dto.AskRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if req.Symbol == "" {
		req.Symbol = "AAPL"
	}

	resp, err := h.askService.Ask(c.Request.Context(), &req)
	if err != nil {
		h.logger.Error("ask failed", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to process question"})
		return
	}

	c.JSON(http.StatusOK, resp)
}

func (h *Handler) AskStream(c *gin.Context) {
	var req dto.AskRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if req.Symbol == "" {
		req.Symbol = "AAPL"
	}

	sc, err := h.askService.PrepareStreamContext(c.Request.Context(), &req)
	if err != nil {
		h.logger.Error("stream retrieval failed", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to process question"})
		return
	}

	genStart := time.Now()

	pyResp, err := h.client.GenerateStream(
		c.Request.Context(), req.Question, sc.ContextChunks,
		string(sc.QueryType), req.Lang, req.History,
	)
	if err != nil {
		h.logger.Error("stream generation request failed", zap.Error(err))
		h.writeSSE(c, "error", map[string]string{"message": "LLM service unavailable"})
		return
	}
	defer pyResp.Body.Close()

	if pyResp.StatusCode >= 400 {
		body, _ := io.ReadAll(pyResp.Body)
		h.logger.Error("python stream error", zap.Int("status", pyResp.StatusCode), zap.String("body", string(body)))
		h.writeSSE(c, "error", map[string]string{"message": "LLM service error"})
		return
	}

	c.Writer.Header().Set("Content-Type", "text/event-stream")
	c.Writer.Header().Set("Cache-Control", "no-cache")
	c.Writer.Header().Set("Connection", "keep-alive")
	c.Writer.Header().Set("X-Accel-Buffering", "no")
	c.Writer.WriteHeaderNow()

	metaEvent := map[string]interface{}{
		"type":       "metadata",
		"query_type": string(sc.QueryType),
		"confidence": sc.Confidence,
		"debug":      sc.Debug,
	}
	h.writeSSE(c, "metadata", metaEvent)

	citationsSent := false

	scanner := bufio.NewScanner(pyResp.Body)
	for scanner.Scan() {
		line := scanner.Text()
		if !strings.HasPrefix(line, "data: ") {
			continue
		}
		payload := line[6:]

		var evt map[string]interface{}
		if err := json.Unmarshal([]byte(payload), &evt); err != nil {
			continue
		}

		evtType, _ := evt["type"].(string)
		switch evtType {
		case "token":
			h.writeSSE(c, "token", evt)

		case "cited_indices":
			// Python parsed the LLM answer and tells us which evidence was actually cited
			filteredCitations := h.filterCitationsByIndices(sc.Citations, evt["indices"])
			citEvent := map[string]interface{}{
				"type":      "citations",
				"citations": filteredCitations,
			}
			h.writeSSE(c, "citations", citEvent)
			citationsSent = true

		case "done":
			if !citationsSent {
				citEvent := map[string]interface{}{
					"type":      "citations",
					"citations": sc.Citations,
				}
				h.writeSSE(c, "citations", citEvent)
			}

			genMs := time.Since(genStart).Milliseconds()
			sc.Debug.GenerationMs = genMs
			sc.Debug.TotalMs += genMs
			doneEvent := map[string]interface{}{
				"type":  "done",
				"debug": sc.Debug,
			}
			h.writeSSE(c, "done", doneEvent)
			return
		}
	}
}

// filterCitationsByIndices returns only the citations at the given 1-based indices.
func (h *Handler) filterCitationsByIndices(allCitations []dto.Citation, rawIndices interface{}) []dto.Citation {
	indices, ok := rawIndices.([]interface{})
	if !ok || len(indices) == 0 {
		return allCitations
	}

	filtered := make([]dto.Citation, 0, len(indices))
	for _, raw := range indices {
		idx, ok := raw.(float64) // JSON numbers decode as float64
		if !ok {
			continue
		}
		i := int(idx) - 1 // convert 1-based to 0-based
		if i >= 0 && i < len(allCitations) {
			filtered = append(filtered, allCitations[i])
		}
	}

	if len(filtered) == 0 {
		return allCitations
	}
	return filtered
}

func (h *Handler) writeSSE(c *gin.Context, event string, data interface{}) {
	jsonBytes, err := json.Marshal(data)
	if err != nil {
		return
	}
	fmt.Fprintf(c.Writer, "event: %s\ndata: %s\n\n", event, string(jsonBytes))
	c.Writer.Flush()
}

func (h *Handler) Metrics(c *gin.Context) {
	symbol := c.DefaultQuery("symbol", "AAPL")
	metric := c.Query("metric")
	yearStr := c.Query("year")

	if metric == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "metric parameter is required"})
		return
	}

	var yearPtr *int
	if yearStr != "" {
		y, err := strconv.Atoi(yearStr)
		if err == nil {
			yearPtr = &y
		}
	}

	resp, err := h.client.Metrics(c.Request.Context(), symbol, metric, yearPtr)
	if err != nil {
		h.logger.Error("metrics query failed", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to query metrics"})
		return
	}

	c.JSON(http.StatusOK, resp)
}

func (h *Handler) Trends(c *gin.Context) {
	symbol := c.DefaultQuery("symbol", "AAPL")
	metric := c.Query("metric")
	startYear, _ := strconv.Atoi(c.DefaultQuery("start_year", "2020"))
	endYear, _ := strconv.Atoi(c.DefaultQuery("end_year", "2025"))

	if metric == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "metric parameter is required"})
		return
	}

	resp, err := h.client.Trends(c.Request.Context(), symbol, metric, startYear, endYear)
	if err != nil {
		h.logger.Error("trends query failed", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to query trends"})
		return
	}

	c.JSON(http.StatusOK, resp)
}

func (h *Handler) Sections(c *gin.Context) {
	resp, err := h.fts.GetSections()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to get sections"})
		return
	}
	c.JSON(http.StatusOK, resp)
}

func (h *Handler) MetricsAvailable(c *gin.Context) {
	symbol := c.DefaultQuery("symbol", "AAPL")
	resp, err := h.client.Health(c.Request.Context())
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	_ = symbol
	c.JSON(http.StatusOK, resp)
}

func (h *Handler) SystemStatus(c *gin.Context) {
	chunks, metrics, years := h.fts.GetCounts()

	pythonStatus := "ok"
	modelsReady := true
	embeddingReady := true
	rerankerReady := true
	llmProvider := ""

	healthResp, err := h.client.Health(c.Request.Context())
	if err != nil {
		pythonStatus = "unavailable"
		modelsReady = false
		embeddingReady = false
		rerankerReady = false
	} else {
		if s, ok := healthResp["status"].(string); ok && s == "warming_up" {
			pythonStatus = "warming_up"
			modelsReady = false
		}
		if v, ok := healthResp["embedding_ready"].(bool); ok {
			embeddingReady = v
		}
		if v, ok := healthResp["reranker_ready"].(bool); ok {
			rerankerReady = v
		}
		if v, ok := healthResp["llm_provider"].(string); ok {
			llmProvider = v
		}
		modelsReady = embeddingReady && rerankerReady
	}

	c.JSON(http.StatusOK, dto.SystemStatus{
		Status:         "ok",
		GoBackend:      "ok",
		PythonService:  pythonStatus,
		ModelsReady:    modelsReady,
		EmbeddingReady: embeddingReady,
		RerankerReady:  rerankerReady,
		LLMProvider:    llmProvider,
		ChunksCount:    chunks,
		MetricsCount:   metrics,
		FiscalYears:    years,
	})
}

func (h *Handler) Healthz(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{"status": "ok"})
}

// ProxyMetricsAvailable forwards to python service
func (h *Handler) ProxyMetricsAvailable(c *gin.Context) {
	symbol := c.DefaultQuery("symbol", "AAPL")
	ctx := c.Request.Context()

	req, _ := http.NewRequestWithContext(ctx, "GET", h.client.BaseURL()+"/metrics/available?symbol="+symbol, nil)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	defer resp.Body.Close()

	c.Status(resp.StatusCode)
	c.Header("Content-Type", "application/json")
	io.Copy(c.Writer, resp.Body)
}
