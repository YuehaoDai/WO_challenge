package retrieval

import (
	"database/sql"
	"fmt"
	"strings"

	"github.com/WO_challenge/go-backend/internal/dto"
	_ "github.com/mattn/go-sqlite3"
)

// FTSSearcher handles SQLite FTS5 full-text search.
type FTSSearcher struct {
	db *sql.DB
}

func NewFTSSearcher(dbPath string) (*FTSSearcher, error) {
	db, err := sql.Open("sqlite3", dbPath+"?mode=ro")
	if err != nil {
		return nil, fmt.Errorf("open sqlite: %w", err)
	}
	return &FTSSearcher{db: db}, nil
}

func (s *FTSSearcher) Close() {
	if s.db != nil {
		s.db.Close()
	}
}

// Search executes FTS5 query and returns ranked results.
func (s *FTSSearcher) Search(query string, topK int, yearFilter *int, sectionFilter *string) ([]dto.ChunkResult, error) {
	ftsQuery := buildFTSQuery(query)

	sqlQuery := `
		SELECT c.id, c.content, c.fiscal_year, c.section_id, c.section_title,
		       bm25(chunks_fts) as score
		FROM chunks_fts
		JOIN chunks c ON c.id = chunks_fts.id
		WHERE chunks_fts MATCH ?
	`
	args := []interface{}{ftsQuery}

	if yearFilter != nil {
		sqlQuery += " AND c.fiscal_year = ?"
		args = append(args, *yearFilter)
	}
	if sectionFilter != nil {
		sqlQuery += " AND c.section_title LIKE ?"
		args = append(args, "%"+*sectionFilter+"%")
	}

	sqlQuery += " ORDER BY score LIMIT ?"
	args = append(args, topK)

	rows, err := s.db.Query(sqlQuery, args...)
	if err != nil {
		return nil, fmt.Errorf("fts query: %w", err)
	}
	defer rows.Close()

	var results []dto.ChunkResult
	for rows.Next() {
		var r dto.ChunkResult
		if err := rows.Scan(&r.ID, &r.Content, &r.FiscalYear, &r.SectionID, &r.SectionTitle, &r.Score); err != nil {
			return nil, fmt.Errorf("scan row: %w", err)
		}
		r.Score = -r.Score // FTS5 bm25 returns negative scores; negate for consistent ranking
		results = append(results, r)
	}

	return results, nil
}

// GetSections returns available fiscal years and sections.
func (s *FTSSearcher) GetSections() (*dto.SectionsResponse, error) {
	yearRows, err := s.db.Query("SELECT DISTINCT fiscal_year FROM chunks ORDER BY fiscal_year")
	if err != nil {
		return nil, err
	}
	defer yearRows.Close()

	var years []int
	for yearRows.Next() {
		var y int
		yearRows.Scan(&y)
		years = append(years, y)
	}

	secRows, err := s.db.Query("SELECT DISTINCT section_id, section_title FROM chunks ORDER BY section_id")
	if err != nil {
		return nil, err
	}
	defer secRows.Close()

	var sections []dto.SectionInfo
	for secRows.Next() {
		var si dto.SectionInfo
		secRows.Scan(&si.SectionID, &si.SectionTitle)
		sections = append(sections, si)
	}

	return &dto.SectionsResponse{Years: years, Sections: sections}, nil
}

// GetCounts returns chunk and metric counts for system status.
func (s *FTSSearcher) GetCounts() (chunks int, metrics int, years []int) {
	s.db.QueryRow("SELECT COUNT(*) FROM chunks").Scan(&chunks)
	s.db.QueryRow("SELECT COUNT(*) FROM metrics").Scan(&metrics)

	yearRows, _ := s.db.Query("SELECT DISTINCT fiscal_year FROM chunks ORDER BY fiscal_year")
	if yearRows != nil {
		defer yearRows.Close()
		for yearRows.Next() {
			var y int
			yearRows.Scan(&y)
			years = append(years, y)
		}
	}
	return
}

var stopWords = map[string]bool{
	"the": true, "is": true, "at": true, "which": true, "on": true,
	"a": true, "an": true, "and": true, "or": true, "not": true,
	"in": true, "to": true, "for": true, "of": true, "with": true,
	"by": true, "from": true, "as": true, "its": true, "it": true,
	"be": true, "are": true, "was": true, "were": true, "been": true,
	"has": true, "have": true, "had": true, "do": true, "does": true,
	"did": true, "will": true, "would": true, "could": true, "should": true,
	"what": true, "how": true, "when": true, "where": true, "who": true,
	"that": true, "this": true, "these": true, "those": true,
}

func buildFTSQuery(query string) string {
	words := strings.Fields(query)
	var terms []string
	for _, w := range words {
		w = strings.Trim(w, ".,;:!?\"'()[]{}+=-")
		lower := strings.ToLower(w)
		if len(w) < 2 || stopWords[lower] {
			continue
		}
		cleaned := strings.Map(func(r rune) rune {
			if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') {
				return r
			}
			return ' '
		}, w)
		for _, part := range strings.Fields(cleaned) {
			if len(part) >= 2 && !stopWords[strings.ToLower(part)] {
				terms = append(terms, part)
			}
		}
	}
	if len(terms) == 0 {
		return query
	}
	return strings.Join(terms, " OR ")
}
