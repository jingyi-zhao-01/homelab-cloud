FROM golang:1.22.5-alpine AS build

ARG TARGETOS=linux
ARG TARGETARCH=amd64

WORKDIR /src

COPY go.mod go.sum ./
COPY main.go ./

RUN go mod download
RUN CGO_ENABLED=0 GOOS=${TARGETOS} GOARCH=${TARGETARCH} go build -o /out/node-disk-janitor ./main.go

FROM alpine:3.20

RUN apk add --no-cache ca-certificates util-linux

WORKDIR /app

COPY --from=build /out/node-disk-janitor /usr/local/bin/node-disk-janitor

ENTRYPOINT ["/usr/local/bin/node-disk-janitor"]
