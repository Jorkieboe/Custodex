# Custodex

Custodex is a local-first visual workbench and RAG dataset preparation editor designed to eliminate the engineering bottleneck in building and maintaining retrieval-augmented generation pipelines through hierarchical chunking, CMS-style metadata extraction, and incremental vector indexing.

See [concept.md](concept.md) for a detailed breakdown of the application's features, logic, and architecture.

## Getting Started

Follow these steps to get your development environment set up and running.

### Prerequisites

Based on the **Custodex** stack, you will need the following tools installed on your system:

- **Git:** For version control.
- **Python 3.11+:** Core runtime for the backend service.
- **uv:** Ultra-fast Python package and virtual environment manager ([astral-sh/uv](https://github.com/astral-sh/uv)).
- **Node.js v18+ & npm:** Runtime for the Vue 3 and Vite frontend application.
- **LM Studio (Optional for local AI):** Local OpenAI-compatible inference server running on `http://localhost:1234/v1`.

### Clone and Initialize the Repository

```bash
git init
git add .
git commit -m "Initial commit from boilerplate"
```

### Install Dependencies & Run

This project uses a unified `go.bat` script to streamline development tasks across Python and Node.js.

To install dependencies for both the Python backend and Vue frontend:

```bash
go.bat i
```

To run both backend and frontend unit test suites:

```bash
go.bat t
```

To start the application:

```bash
go.bat
```

Once running:
- The FastAPI backend will be available at `http://localhost:8000` (interactive documentation at `/docs`).
- The Vite frontend will be available at `http://localhost:5173`.

### Commands

Run common project tasks via `go.bat`:
- `go`: Runs the application.
- `go i`: Installs Python (uv) and Node (npm) dependencies.
- `go t`: Runs Pytest backend and Vitest frontend unit tests.
- `go cmd`: Opens a shell with the Python virtual environment activated.
- `go f`: Freezes Python dependencies to `requirements.txt`.
- `go b`: Compiles frontend assets and packages the desktop binary via PyInstaller.