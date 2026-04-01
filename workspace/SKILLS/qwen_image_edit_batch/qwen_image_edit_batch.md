---
name: qwen_image_edit_batch
description: Batch image editing using Qwen model served via ASG. Reads a CSV of tasks (with instructions and image references), sends each to the Qwen image-edit API, and saves output images.
---

# Qwen Image Edit Batch Skill

Batch-process image editing tasks (virtual try-on, style transfer, product editing, etc.) using a Qwen model served on an ASG instance.

## Prerequisites

- Python 3 with `requests` installed (`pip install requests`)
- Access to a running Qwen image-edit ASG endpoint (or SSH access to tunnel to one)

## Known ASG Endpoints

| Instance | Host | Port |
|----------|------|------|
| p4de | `ec2-18-206-77-68.compute-1.amazonaws.com` | 8001 |
| p5en | `34.211.247.63` | 8001 |

## Input CSV Format

The CSV must have a header row with these columns:

```
Type,Benchmark,Task,Instruction,Images
```

- **Type**: e.g. `Edit`
- **Benchmark**: e.g. `Virtual Try-On`
- **Task**: task description
- **Instruction**: the text prompt sent to the model (e.g. "Put this denim jacket on me")
- **Images**: semicolon-separated image filenames relative to `--image_dir`
  - e.g. `portrait_men_0.png; clothing_jacket_0.png; clothing_jacket_1.png`

Example row:
```
Edit,Virtual Try-On,Place clothing onto a user body,Put this denim jacket on me,portrait_men_casual_jacket_outfit_model_0.png; clothing_denim_jacket_men_0.png
```

## Usage

### Basic (direct connection — API already accessible on localhost or a reachable host)

```bash
python workspace/SKILLS/qwen_image_edit_batch/script.py \
    --csv workspace/MISSIONS/build_mm_train/mm_shopping_benchmark_train/samples.csv \
    --image_dir workspace/MISSIONS/build_mm_train/mm_shopping_benchmark_train/images \
    --output_dir workspace/MISSIONS/build_mm_train/mm_shopping_benchmark_train/output \
    --host 34.211.247.63 --port 8001
```

### With SSH tunnel to remote ASG

```bash
python workspace/SKILLS/qwen_image_edit_batch/script.py \
    --csv workspace/MISSIONS/build_mm_train/mm_shopping_benchmark_train/samples.csv \
    --image_dir workspace/MISSIONS/build_mm_train/mm_shopping_benchmark_train/images \
    --output_dir workspace/MISSIONS/build_mm_train/mm_shopping_benchmark_train/output \
    --remote_host ec2-18-206-77-68.compute-1.amazonaws.com \
    --remote_port 8001
```

### Process a subset of rows

```bash
python workspace/SKILLS/qwen_image_edit_batch/script.py \
    --csv samples.csv --image_dir images/ --output_dir output/ \
    --host localhost --port 8001 \
    --start_row 100 --end_row 200
```

## CLI Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--csv` | ✅ | — | Path to input CSV file |
| `--image_dir` | ✅ | — | Directory containing source images |
| `--output_dir` | ✅ | — | Directory for output images and results |
| `--host` | | `localhost` | API host |
| `--port` | | `8001` | API port |
| `--remote_host` | | — | Remote host for auto SSH tunnel |
| `--remote_port` | | `8001` | Remote port to tunnel |
| `--local_port` | | `8001` | Local port for SSH tunnel |
| `--num_inference_steps` | | `50` | Diffusion steps |
| `--guidance_scale` | | `1.0` | Guidance scale |
| `--seed` | | `0` | Random seed |
| `--max_retries` | | `3` | Max retries per failed row |
| `--retry_delay` | | `5.0` | Seconds between retries |
| `--start_row` | | `0` | First row index to process (0-based) |
| `--end_row` | | all | End row index (exclusive) |

## Output

- **Images**: Saved as `output_XXXXX.png` in `--output_dir`
- **Results CSV**: `results.csv` in `--output_dir` — same columns as input plus:
  - `Output`: output image filename
  - `Status`: `OK` or `ERROR`
  - `Error`: error message if failed
- **Progress file**: `.progress` in `--output_dir` — tracks completed row indices for **automatic resume**. Re-running the same command skips already-completed rows.

## Resume / Re-run

The script automatically resumes from where it left off. Completed row indices are tracked in `.progress`. To start fresh, delete the `.progress` file and `results.csv` in the output directory.

## API Details

Each row is sent as a POST to `http://<host>:<port>/v1/chat/completions` with:
- `messages[0].content` = text prompt + image data URLs
- `extra_body` = model parameters (steps, guidance, seed, etc.)
- `guidance_scale` = 4.0 (top-level payload)

The response image is extracted from `choices[0].message.content[0].image_url.url`.

## Script Location

```
workspace/SKILLS/qwen_image_edit_batch/script.py
```
