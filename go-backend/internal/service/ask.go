package service

import (
	"context"
	"time"

	"github.com/WO_challenge/go-backend/internal/classifier"
	"github.com/WO_challenge/go-backend/internal/config"
	"github.com/WO_challenge/go-backend/internal/dto"
	"github.com/WO_challenge/go-backend/internal/modelclient"
	"github.com/WO_challenge/go-backend/internal/retrieval"
	"go.uber.org/zap"
)

// AskService orchestrates the full question-answering pipeline.
type AskService struct {
	retriever *retrieval.HybridRetriever
	client    *modelclient.Client
	cfg       *config.RetrievalConfig
	logger    *zap.Logger
}

func NewAskService(retriever *retrieval.HybridRetriever, client *modelclient.Client, cfg *config.RetrievalConfig, logger *zap.Logger) *AskService {
	return &AskService{
		retriever: retriever,
		client:    client,
		cfg:       cfg,
		logger:    logger,
	}
}

func (s *AskService) Ask(ctx context.Context, req *dto.AskRequest) (*dto.AskResponse, error) {
	totalStart := time.Now()

	queryType, years, _ := classifier.Classify(req.Question)
	s.logger.Info("classified query",
		zap.String("type", string(queryType)),
		zap.Ints("years", years),
		zap.String("question", req.Question),
	)

	if queryType == dto.QueryMetric && len(years) <= 1 {
		return s.handleMetricQuery(ctx, req, queryType, years, totalStart)
	}

	return s.handleRetrievalQuery(ctx, req, queryType, years, totalStart)
}

func (s *AskService) handleMetricQuery(ctx context.Context, req *dto.AskRequest, queryType dto.QueryType, years []int, totalStart time.Time) (*dto.AskResponse, error) {
	// For metric queries, still do retrieval to provide context and citations
	return s.handleRetrievalQuery(ctx, req, queryType, years, totalStart)
}

func (s *AskService) handleRetrievalQuery(ctx context.Context, req *dto.AskRequest, queryType dto.QueryType, years []int, totalStart time.Time) (*dto.AskResponse, error) {
	retrievalStart := time.Now()

	var yearFilter *int
	if len(years) == 1 {
		yearFilter = &years[0]
	}

	topK := s.cfg.ContextTopK
	if req.TopK > 0 {
		topK = req.TopK
	}

	results, ftsHits, denseHits, rrfCount, rerankCount, err := s.retriever.Search(
		ctx, req.Question,
		s.cfg.FTSTopK, s.cfg.DenseTopK, s.cfg.RerankTopK,
		yearFilter,
	)
	if err != nil {
		s.logger.Error("retrieval failed", zap.Error(err))
		return nil, err
	}

	retrievalMs := time.Since(retrievalStart).Milliseconds()

	if len(results) > topK {
		results = results[:topK]
	}

	contextChunks := make([]map[string]interface{}, 0, len(results))
	for _, r := range results {
		contextChunks = append(contextChunks, map[string]interface{}{
			"id":            r.ID,
			"fiscal_year":   r.FiscalYear,
			"section_title": r.SectionTitle,
			"text":          r.Content,
		})
	}

	genStart := time.Now()
	genResp, err := s.client.Generate(ctx, req.Question, contextChunks, string(queryType), req.Lang, req.History)
	if err != nil {
		s.logger.Error("generation failed, returning retrieval results only", zap.Error(err))
		citations := make([]dto.Citation, 0, len(results))
		for _, r := range results {
			snippet := r.Content
			if len(snippet) > 200 {
				snippet = snippet[:200] + "..."
			}
			citations = append(citations, dto.Citation{
				ChunkID:      r.ID,
				FiscalYear:   r.FiscalYear,
				SectionTitle: r.SectionTitle,
				Snippet:      snippet,
			})
		}
		return &dto.AskResponse{
			QueryType:  queryType,
			Answer:     "LLM service unavailable. Here are the most relevant evidence chunks from the 10-K filings.",
			Citations:  citations,
			Confidence: "low",
			Debug: dto.DebugInfo{
				QueryType:     string(queryType),
				RetrievalMs:   retrievalMs,
				FTSHits:       ftsHits,
				DenseHits:     denseHits,
				AfterRRF:      rrfCount,
				AfterRerank:   rerankCount,
				ContextChunks: len(results),
				GenerationMs:  0,
				TotalMs:       time.Since(totalStart).Milliseconds(),
			},
		}, nil
	}
	genMs := time.Since(genStart).Milliseconds()

	confidence := "high"
	if len(results) <= 1 {
		confidence = "low"
	} else if len(results) <= 3 {
		confidence = "medium"
	}

	return &dto.AskResponse{
		QueryType:  queryType,
		Answer:     genResp.Answer,
		Citations:  genResp.Citations,
		Confidence: confidence,
		Debug: dto.DebugInfo{
			QueryType:     string(queryType),
			RetrievalMs:   retrievalMs,
			FTSHits:       ftsHits,
			DenseHits:     denseHits,
			AfterRRF:      rrfCount,
			AfterRerank:   rerankCount,
			ContextChunks: len(results),
			GenerationMs:  genMs,
			TotalMs:       time.Since(totalStart).Milliseconds(),
		},
	}, nil
}
