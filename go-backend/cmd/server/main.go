package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
	"go.uber.org/zap"

	"github.com/WO_challenge/go-backend/internal/config"
	"github.com/WO_challenge/go-backend/internal/handler"
	"github.com/WO_challenge/go-backend/internal/modelclient"
	"github.com/WO_challenge/go-backend/internal/retrieval"
	"github.com/WO_challenge/go-backend/internal/service"
)

func main() {
	cfgPath := os.Getenv("CONFIG_PATH")
	if cfgPath == "" {
		cfgPath = "/app/configs/app.yaml"
	}

	cfg, err := config.Load(cfgPath)
	if err != nil {
		log.Fatalf("Failed to load config: %v", err)
	}

	logger, _ := zap.NewProduction()
	defer logger.Sync()

	fts, err := retrieval.NewFTSSearcher(cfg.SQLite.Path)
	if err != nil {
		logger.Warn("FTS searcher init failed — will retry on first request", zap.Error(err))
	}

	client := modelclient.New(cfg.PythonService.BaseURL, cfg.PythonService.Timeout)

	hybridRetriever := retrieval.NewHybridRetriever(fts, client, cfg.Retrieval.RRFK)
	askService := service.NewAskService(hybridRetriever, client, &cfg.Retrieval, logger)

	h := handler.New(askService, client, fts, logger)

	gin.SetMode(gin.ReleaseMode)
	r := gin.New()
	r.Use(gin.Recovery())
	r.Use(cors.New(cors.Config{
		AllowOrigins:     []string{"*"},
		AllowMethods:     []string{"GET", "POST", "OPTIONS"},
		AllowHeaders:     []string{"Content-Type", "Authorization"},
		ExposeHeaders:    []string{"Content-Length"},
		AllowCredentials: true,
		MaxAge:           12 * time.Hour,
	}))

	r.Use(func(c *gin.Context) {
		start := time.Now()
		c.Next()
		logger.Info("request",
			zap.String("method", c.Request.Method),
			zap.String("path", c.Request.URL.Path),
			zap.Int("status", c.Writer.Status()),
			zap.Duration("latency", time.Since(start)),
		)
	})

	r.GET("/healthz", h.Healthz)

	api := r.Group("/api/v1")
	{
		api.POST("/ask", h.Ask)
		api.POST("/ask/stream", h.AskStream)
		api.GET("/metrics", h.Metrics)
		api.GET("/trends", h.Trends)
		api.GET("/sections", h.Sections)
		api.GET("/metrics/available", h.ProxyMetricsAvailable)
		api.GET("/system/status", h.SystemStatus)
	}

	addr := fmt.Sprintf(":%d", cfg.Server.Port)
	logger.Info("Starting Go backend", zap.String("addr", addr))

	srv := &http.Server{
		Addr:         addr,
		Handler:      r,
		ReadTimeout:  cfg.Server.ReadTimeout,
		WriteTimeout: cfg.Server.WriteTimeout,
	}

	if err := srv.ListenAndServe(); err != nil {
		logger.Fatal("Server failed", zap.Error(err))
	}
}
