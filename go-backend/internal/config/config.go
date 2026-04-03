package config

import (
	"os"
	"time"

	"gopkg.in/yaml.v3"
)

type Config struct {
	Server        ServerConfig        `yaml:"server"`
	PythonService PythonServiceConfig `yaml:"python_service"`
	Retrieval     RetrievalConfig     `yaml:"retrieval"`
	SQLite        SQLiteConfig        `yaml:"sqlite"`
	Log           LogConfig           `yaml:"log"`
}

type ServerConfig struct {
	Port         int           `yaml:"port"`
	ReadTimeout  time.Duration `yaml:"read_timeout"`
	WriteTimeout time.Duration `yaml:"write_timeout"`
}

type PythonServiceConfig struct {
	BaseURL string        `yaml:"base_url"`
	Timeout time.Duration `yaml:"timeout"`
}

type RetrievalConfig struct {
	FTSTopK     int `yaml:"fts_top_k"`
	DenseTopK   int `yaml:"dense_top_k"`
	RRFK        int `yaml:"rrf_k"`
	RerankTopK  int `yaml:"rerank_top_k"`
	ContextTopK int `yaml:"context_top_k"`
}

type SQLiteConfig struct {
	Path string `yaml:"path"`
}

type LogConfig struct {
	Level  string `yaml:"level"`
	Format string `yaml:"format"`
}

func Load(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}

	cfg := &Config{
		Server: ServerConfig{
			Port:         8080,
			ReadTimeout:  30 * time.Second,
			WriteTimeout: 60 * time.Second,
		},
		PythonService: PythonServiceConfig{
			BaseURL: "http://python-service:8000",
			Timeout: 30 * time.Second,
		},
		Retrieval: RetrievalConfig{
			FTSTopK:     20,
			DenseTopK:   20,
			RRFK:        60,
			RerankTopK:  8,
			ContextTopK: 5,
		},
	}

	if err := yaml.Unmarshal(data, cfg); err != nil {
		return nil, err
	}

	return cfg, nil
}
