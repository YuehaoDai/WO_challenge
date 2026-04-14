package modelclient

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/WO_challenge/go-backend/internal/dto"
)

// Client communicates with the Python model service.
type Client struct {
	baseURL    string
	httpClient *http.Client
}

func New(baseURL string, timeout time.Duration) *Client {
	return &Client{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: timeout,
		},
	}
}

func (c *Client) BaseURL() string {
	return c.baseURL
}

func (c *Client) doJSON(ctx context.Context, method, path string, reqBody, respBody interface{}) error {
	var body io.Reader
	if reqBody != nil {
		data, err := json.Marshal(reqBody)
		if err != nil {
			return fmt.Errorf("marshal request: %w", err)
		}
		body = bytes.NewReader(data)
	}

	req, err := http.NewRequestWithContext(ctx, method, c.baseURL+path, body)
	if err != nil {
		return fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("request to python service: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		respData, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("python service error (status %d): %s", resp.StatusCode, string(respData))
	}

	if respBody != nil {
		if err := json.NewDecoder(resp.Body).Decode(respBody); err != nil {
			return fmt.Errorf("decode response: %w", err)
		}
	}

	return nil
}

func (c *Client) DenseSearch(ctx context.Context, query string, topK int, filters map[string]interface{}) (*dto.DenseSearchResponse, error) {
	req := dto.DenseSearchRequest{Query: query, TopK: topK, Filters: filters}
	var resp dto.DenseSearchResponse
	if err := c.doJSON(ctx, "POST", "/search/dense", req, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

func (c *Client) Rerank(ctx context.Context, query string, docs []dto.RerankDocument, topK int) (*dto.RerankResponse, error) {
	req := dto.RerankRequest{Query: query, Documents: docs, TopK: topK}
	var resp dto.RerankResponse
	if err := c.doJSON(ctx, "POST", "/rerank", req, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

func (c *Client) Generate(ctx context.Context, question string, contextChunks []map[string]interface{}, queryType string, lang string, history []dto.HistoryMessage) (*dto.GenerateResponse, error) {
	req := dto.GenerateRequest{
		Question:  question,
		Context:   contextChunks,
		QueryType: queryType,
		Stream:    false,
		Lang:      lang,
		History:   history,
	}
	var resp dto.GenerateResponse
	if err := c.doJSON(ctx, "POST", "/generate", req, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

// GenerateStream returns the raw HTTP response for SSE streaming.
func (c *Client) GenerateStream(ctx context.Context, question string, contextChunks []map[string]interface{}, queryType string, lang string, history []dto.HistoryMessage) (*http.Response, error) {
	req := dto.GenerateRequest{
		Question:  question,
		Context:   contextChunks,
		QueryType: queryType,
		Stream:    true,
		Lang:      lang,
		History:   history,
	}
	data, err := json.Marshal(req)
	if err != nil {
		return nil, err
	}

	httpReq, err := http.NewRequestWithContext(ctx, "POST", c.baseURL+"/generate/stream", bytes.NewReader(data))
	if err != nil {
		return nil, err
	}
	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("Accept", "text/event-stream")

	return c.httpClient.Do(httpReq)
}

func (c *Client) Health(ctx context.Context) (map[string]interface{}, error) {
	var resp map[string]interface{}
	if err := c.doJSON(ctx, "GET", "/health", nil, &resp); err != nil {
		return nil, err
	}
	return resp, nil
}

// Metrics forwards a metrics request to the Python service.
func (c *Client) Metrics(ctx context.Context, symbol, metric string, fiscalYear *int) (map[string]interface{}, error) {
	body := map[string]interface{}{
		"symbol": symbol,
		"metric": metric,
	}
	if fiscalYear != nil {
		body["fiscal_year"] = *fiscalYear
	}
	var resp map[string]interface{}
	if err := c.doJSON(ctx, "POST", "/metrics", body, &resp); err != nil {
		return nil, err
	}
	return resp, nil
}

// Trends forwards a trends request to the Python service.
func (c *Client) Trends(ctx context.Context, symbol, metric string, startYear, endYear int) (map[string]interface{}, error) {
	body := map[string]interface{}{
		"symbol":     symbol,
		"metric":     metric,
		"start_year": startYear,
		"end_year":   endYear,
	}
	var resp map[string]interface{}
	if err := c.doJSON(ctx, "POST", "/trends", body, &resp); err != nil {
		return nil, err
	}
	return resp, nil
}
