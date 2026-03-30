# MM Shopping Benchmark — Annotation Editor

A web-based UI for viewing, editing, and managing the MM Shopping Benchmark dataset.

## Project Structure

```
mm_shopping_benchmark/
├── editor_server.py      # Python HTTP server (backend)
├── editor.html            # Web UI (frontend)
├── samples.csv            # Benchmark dataset
├── images/                # All product/model images (416 files)
├── backups/               # Auto-created CSV backups (last 50 kept)
├── viewer.html            # Read-only viewer
├── image_metadata.json    # Image metadata
└── *.json                 # Other metadata files
```

## Quick Start

### 1. Kill any existing process on the port (if needed)

```bash
lsof -ti:8765 | xargs kill -9
```

### 2. Start the server

```bash
cd ./workspace/MISSIONS/build_mm_shopping_benchmark/mm_shopping_benchmark
python3 editor_server.py
```

Server runs on **http://localhost:8765** by default.

To use a custom port:

```bash
python3 editor_server.py 9000
```

To run in background:

```bash
python3 editor_server.py &
```

### 3. Open in browser

Go to: **http://localhost:8765/**

## Dataset Fields

| Field         | Description                                        | Example                              |
|---------------|----------------------------------------------------|--------------------------------------|
| **Type**      | `Edit` or `Gen`                                    | `Edit`                               |
| **Benchmark** | Task category                                      | `Virtual Try-On`                     |
| **Task**      | Task description                                   | `Place one or more clothing items onto a user body` |
| **Instruction** | Natural language prompt                          | `Place this jacket on me please`     |
| **Images**    | Semicolon-separated image filenames from `images/` | `model_001.jpg; jacket_002.jpg`      |

## Editor Features

- **Browse & Filter** — filter by Type, Benchmark, Task, or free-text search
- **Inline Image Preview** — see referenced images directly in the UI
- **Edit** — modify any field of any sample
- **Add** — create new samples (with optional insert position)
- **Delete** — remove one or multiple samples
- **Duplicate** — clone a sample
- **Reorder** — move samples up/down
- **Auto-Backup** — every save creates a timestamped backup in `backups/` (max 50)

## API Reference

All endpoints return JSON. POST endpoints accept JSON body.

### Read

| Method | Endpoint        | Description              |
|--------|-----------------|--------------------------|
| GET    | `/api/samples`  | Get all samples          |
| GET    | `/api/images`   | List all image filenames |

### Write

| Method | Endpoint                 | Body                                      | Description              |
|--------|--------------------------|-------------------------------------------|--------------------------|
| POST   | `/api/samples/update`    | `{"index": 0, "sample": {...}}`           | Update sample at index   |
| POST   | `/api/samples/add`       | `{"sample": {...}, "insertAt": 5}`        | Add new sample           |
| POST   | `/api/samples/delete`    | `{"indices": [0, 3, 5]}`                  | Delete by indices        |
| POST   | `/api/samples/duplicate` | `{"index": 2}`                            | Duplicate sample         |
| POST   | `/api/samples/reorder`   | `{"from": 2, "to": 5}`                   | Move sample position     |
| POST   | `/api/samples/save`      | `{"samples": [...]}`                      | Full dataset overwrite   |

### API Examples

```bash
# Get all samples
curl -s http://localhost:8765/api/samples | python3 -m json.tool

# List available images
curl -s http://localhost:8765/api/images

# Update instruction of sample #0
curl -X POST http://localhost:8765/api/samples/update \
  -H "Content-Type: application/json" \
  -d '{"index": 0, "sample": {"Instruction": "Try this dress on me"}}'

# Add a new sample
curl -X POST http://localhost:8765/api/samples/add \
  -H "Content-Type: application/json" \
  -d '{"sample": {"Type": "Edit", "Benchmark": "Virtual Try-On", "Task": "Place clothing on body", "Instruction": "Show me in this shirt", "Images": "image1.jpg; image2.jpg"}}'

# Delete samples at index 1 and 3
curl -X POST http://localhost:8765/api/samples/delete \
  -H "Content-Type: application/json" \
  -d '{"indices": [1, 3]}'
```

## Requirements

- Python 3 (no external dependencies — uses only stdlib)

## Stopping the Server

- **Foreground**: Press `Ctrl+C`
- **Background**: `lsof -ti:8765 | xargs kill -9`
