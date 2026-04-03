package dto

// QueryType classifies user questions into routing categories.
type QueryType string

const (
	QueryNarrative   QueryType = "narrative"
	QueryMetric      QueryType = "metric"
	QueryComparative QueryType = "comparative"
	QueryReport      QueryType = "report"
)

type HistoryMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type AskRequest struct {
	Question string           `json:"question" binding:"required,min=1"`
	Symbol   string           `json:"symbol"`
	TopK     int              `json:"top_k"`
	Stream   bool             `json:"stream"`
	Lang     string           `json:"lang"`
	History  []HistoryMessage `json:"history,omitempty"`
}

type AskResponse struct {
	QueryType  QueryType  `json:"query_type"`
	Answer     string     `json:"answer"`
	Citations  []Citation `json:"citations"`
	Confidence string     `json:"confidence"`
	Debug      DebugInfo  `json:"debug,omitempty"`
}

type Citation struct {
	ChunkID      string `json:"chunk_id"`
	FiscalYear   int    `json:"fiscal_year"`
	SectionTitle string `json:"section_title"`
	Snippet      string `json:"snippet"`
}

type DebugInfo struct {
	QueryType      string  `json:"query_type"`
	RetrievalMs    int64   `json:"retrieval_time_ms"`
	FTSHits        int     `json:"fts_hits"`
	DenseHits      int     `json:"dense_hits"`
	AfterRRF       int     `json:"after_rrf"`
	AfterRerank    int     `json:"after_rerank"`
	ContextChunks  int     `json:"context_chunks"`
	GenerationMs   int64   `json:"generation_time_ms"`
	TotalMs        int64   `json:"total_time_ms"`
}

type ChunkResult struct {
	ID           string  `json:"chunk_id"`
	Content      string  `json:"content"`
	Score        float64 `json:"score"`
	FiscalYear   int     `json:"fiscal_year"`
	SectionID    int     `json:"section_id"`
	SectionTitle string  `json:"section_title"`
}

// Python service request/response types

type EmbedRequest struct {
	Texts []string `json:"texts"`
}

type EmbedResponse struct {
	Embeddings [][]float64 `json:"embeddings"`
	Model      string      `json:"model"`
	Dimension  int         `json:"dimension"`
}

type RerankRequest struct {
	Query     string           `json:"query"`
	Documents []RerankDocument `json:"documents"`
	TopK      int              `json:"top_k"`
}

type RerankDocument struct {
	ID   string `json:"id"`
	Text string `json:"text"`
}

type RerankResponse struct {
	Results []RankedDoc `json:"results"`
}

type RankedDoc struct {
	ID    string  `json:"id"`
	Text  string  `json:"text"`
	Score float64 `json:"score"`
	Rank  int     `json:"rank"`
}

type DenseSearchRequest struct {
	Query   string            `json:"query"`
	TopK    int               `json:"top_k"`
	Filters map[string]interface{} `json:"filters,omitempty"`
}

type DenseSearchResponse struct {
	Results []DenseResult `json:"results"`
}

type DenseResult struct {
	ChunkID      string  `json:"chunk_id"`
	Score        float64 `json:"score"`
	FiscalYear   int     `json:"fiscal_year"`
	SectionID    int     `json:"section_id"`
	SectionTitle string  `json:"section_title"`
	Content      string  `json:"content"`
}

type GenerateRequest struct {
	Question  string                   `json:"question"`
	Context   []map[string]interface{} `json:"context"`
	QueryType string                   `json:"query_type"`
	Stream    bool                     `json:"stream"`
	Lang      string                   `json:"lang,omitempty"`
	History   []HistoryMessage         `json:"history,omitempty"`
}

type GenerateResponse struct {
	Answer    string     `json:"answer"`
	Citations []Citation `json:"citations"`
	Model     string     `json:"model"`
}

type SectionsResponse struct {
	Years    []int           `json:"years"`
	Sections []SectionInfo   `json:"sections"`
}

type SectionInfo struct {
	SectionID    int    `json:"section_id"`
	SectionTitle string `json:"section_title"`
}

type SystemStatus struct {
	Status         string `json:"status"`
	GoBackend      string `json:"go_backend"`
	PythonService  string `json:"python_service"`
	ModelsReady    bool   `json:"models_ready"`
	EmbeddingReady bool   `json:"embedding_ready"`
	RerankerReady  bool   `json:"reranker_ready"`
	LLMProvider    string `json:"llm_provider"`
	ChunksCount    int    `json:"chunks_count"`
	MetricsCount   int    `json:"metrics_count"`
	FiscalYears    []int  `json:"fiscal_years"`
}
