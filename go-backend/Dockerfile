FROM golang:1.22-alpine AS builder

WORKDIR /build

RUN apk add --no-cache gcc musl-dev

COPY go.mod go.sum* ./
RUN go mod download 2>/dev/null || true

COPY . .

RUN CGO_ENABLED=1 GOOS=linux go build -tags sqlite_fts5 -o server ./cmd/server/

FROM alpine:3.19

WORKDIR /app

RUN apk add --no-cache ca-certificates sqlite-libs

COPY --from=builder /build/server /app/server

EXPOSE 8080

CMD ["/app/server"]
