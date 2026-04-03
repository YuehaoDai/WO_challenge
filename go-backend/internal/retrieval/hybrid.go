package retrieval

import (
	"context"
	"log"
	"sort"

	"github.com/WO_challenge/go-backend/internal/dto"
	"github.com/WO_challenge/go-backend/internal/modelclient"
)

// HybridRetriever combines FTS5 and FAISS dense search with RRF fusion.
type HybridRetriever struct {
	fts    *FTSSearcher
	client *modelclient.Client
	rrfK   int
}

func NewHybridRetriever(fts *FTSSearcher, client *modelclient.Client, rrfK int) *HybridRetriever {
	return &HybridRetriever{fts: fts, client: client, rrfK: rrfK}
}

// Search performs hybrid retrieval: FTS5 + dense, fused via RRF, then reranked.
func (h *HybridRetriever) Search(ctx context.Context, query string, ftsTopK, denseTopK, rerankTopK int, yearFilter *int) ([]dto.ChunkResult, int, int, int, int, error) {
	ftsResults, err := h.fts.Search(query, ftsTopK, yearFilter, nil)
	if err != nil {
		log.Printf("[WARN] FTS search error: %v", err)
		ftsResults = nil
	}
	ftsCount := len(ftsResults)

	denseResp, err := h.client.DenseSearch(ctx, query, denseTopK, nil)
	denseCount := 0
	var denseResults []dto.ChunkResult
	if err == nil && denseResp != nil {
		for _, r := range denseResp.Results {
			if yearFilter != nil && r.FiscalYear != *yearFilter {
				continue
			}
			denseResults = append(denseResults, dto.ChunkResult{
				ID:           r.ChunkID,
				Content:      r.Content,
				Score:        r.Score,
				FiscalYear:   r.FiscalYear,
				SectionID:    r.SectionID,
				SectionTitle: r.SectionTitle,
			})
		}
		denseCount = len(denseResults)
	}

	fused := rrfFusion(ftsResults, denseResults, h.rrfK)
	rrfCount := len(fused)

	if len(fused) == 0 {
		return nil, ftsCount, denseCount, 0, 0, nil
	}

	docs := make([]dto.RerankDocument, 0, len(fused))
	contentMap := map[string]dto.ChunkResult{}
	for _, r := range fused {
		docs = append(docs, dto.RerankDocument{ID: r.ID, Text: r.Content})
		contentMap[r.ID] = r
	}

	rerankResp, err := h.client.Rerank(ctx, query, docs, rerankTopK)
	if err != nil {
		if len(fused) > rerankTopK {
			fused = fused[:rerankTopK]
		}
		return fused, ftsCount, denseCount, rrfCount, len(fused), nil
	}

	var reranked []dto.ChunkResult
	for _, rd := range rerankResp.Results {
		if orig, ok := contentMap[rd.ID]; ok {
			orig.Score = rd.Score
			reranked = append(reranked, orig)
		}
	}
	return reranked, ftsCount, denseCount, rrfCount, len(reranked), nil
}

// rrfFusion merges two ranked lists using Reciprocal Rank Fusion.
func rrfFusion(listA, listB []dto.ChunkResult, k int) []dto.ChunkResult {
	scores := map[string]float64{}
	docs := map[string]dto.ChunkResult{}

	for rank, r := range listA {
		scores[r.ID] += 1.0 / float64(k+rank+1)
		docs[r.ID] = r
	}
	for rank, r := range listB {
		scores[r.ID] += 1.0 / float64(k+rank+1)
		if _, exists := docs[r.ID]; !exists {
			docs[r.ID] = r
		}
	}

	type scored struct {
		id    string
		score float64
	}
	var sorted_list []scored
	for id, s := range scores {
		sorted_list = append(sorted_list, scored{id, s})
	}
	sort.Slice(sorted_list, func(i, j int) bool {
		return sorted_list[i].score > sorted_list[j].score
	})

	var results []dto.ChunkResult
	for _, s := range sorted_list {
		r := docs[s.id]
		r.Score = s.score
		results = append(results, r)
	}

	return results
}
