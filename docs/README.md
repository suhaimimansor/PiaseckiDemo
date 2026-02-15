# Documentation

This directory contains all project documentation in Markdown and PDF format.

## Structure

```
docs/
├── README.md                 # This file
├── architecture/             # System architecture and design documents
├── api/                      # API reference documentation
├── guides/                   # Setup, deployment, and user guides
└── specs/                    # Technical specifications and protocols
```

## Formats

- **Markdown (`.md`)** — Source documentation, version-controlled
- **PDF (`.pdf`)** — Generated/exported documents for distribution

## Contents

| Document | Format | Description |
|---|---|---|
| *Architecture Overview* | md | System architecture, service interactions, data flow |
| *API Reference* | md | REST endpoints and WebSocket events per service |
| *Setup Guide* | md | Local development, Podman, and Kubernetes setup |
| *Flight Compute Spec* | md | C library API, MISRA compliance notes |
| *Telemetry Protocol Spec* | md | Binary protocol format for hardware integration |
