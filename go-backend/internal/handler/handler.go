package handler

import (
	"io"
	"net/http"
	"strconv"

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

	resp, err := h.askService.Ask(c.Request.Context(), &req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, resp)
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
