#!/usr/bin/env python3
"""
Qwen Image Edit Batch Script
=============================
Batch-process image editing tasks from a CSV file using Qwen model served via ASG.

Usage:
    python script.py --csv <path/to/samples.csv> --image_dir <path/to/images/> --output_dir <path/to/output/> [options]

CSV Format (header required):
    Type,Benchmark,Task,Instruction,Images
    - Images column: semicolon-separated filenames relative to --image_dir
      e.g. "portrait_men_0.png; clothing_jacket_0.png; clothing_jacket_1.png"

The script:
  1. Reads the CSV
  2. Encodes each referenced image as a base64 data URL
  3. Sends (prompt + images) to the Qwen image-edit endpoint
  4. Saves the returned image to --output_dir
  5. Writes a results CSV with an extra "Output" column
"""

import argparse
import base64
import csv
import json
import logging
import mimetypes
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Core API call
# ──────────────────────────────────────────────────────────────────────────────

def call_qwen_image_edition(
        images=None,
        prompt=None,
        negative_prompt=None,
        height=None,
        width=None,
        cfg_scale=None,
        num_inference_steps=50,
        guidance_scale=1.0,
        seed=0,
        resolution=None,
        layers=None,
        host="localhost",
        port=8001):
    """
    Call the Qwen image-edit endpoint.

    Args:
        images: list of image data-URLs (base64) or http(s) URLs.
        prompt: text instruction for the edit.
        negative_prompt: things to avoid.
        height / width: output dimensions.
        cfg_scale: classifier-free guidance scale.
        num_inference_steps: diffusion steps.
        guidance_scale: guidance scale.
        seed: random seed.
        resolution: output resolution string.
        layers: layer specification.
        host: API host (default localhost, use with SSH tunnel).
        port: API port.

    Returns:
        base64 data-URL string of the generated image.
    """
    content = [
        {"type": "text", "text": prompt}
    ] + [{"type": "image_url", "image_url": {"url": image}} for image in images]

    messages = [{"role": "user", "content": content}]

    extra_body = {}
    if num_inference_steps is not None:
        extra_body["num_inference_steps"] = num_inference_steps
    if guidance_scale is not None:
        extra_body["guidance_scale"] = guidance_scale
    if seed is not None:
        extra_body["seed"] = seed
    if negative_prompt is not None:
        extra_body["negative_prompt"] = negative_prompt
    if width is not None:
        extra_body["width"] = width
    if height is not None:
        extra_body["height"] = height
    if cfg_scale is not None:
        extra_body["cfg_scale"] = cfg_scale
    if resolution is not None:
        extra_body["resolution"] = resolution
    if layers is not None:
        extra_body["layers"] = layers

    payload = {"messages": messages}
    payload["guidance_scale"] = 4.0
    if extra_body:
        payload["extra_body"] = extra_body

    url = f"http://{host}:{port}/v1/chat/completions"
    resp = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=600,
    )
    resp.raise_for_status()
    resp_json = resp.json()
    output = resp_json["choices"][0]["message"]["content"][0]["image_url"]["url"]
    return output


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def image_to_data_url(filepath: str) -> str:
    """Convert a local image file to a base64 data URL."""
    mime, _ = mimetypes.guess_type(filepath)
    if mime is None:
        mime = "image/png"
    with open(filepath, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def save_data_url_image(data_url: str, output_path: str):
    """Save a base64 data-URL string to a file."""
    # data:image/png;base64,iVBOR...
    match = re.match(r"data:image/(\w+);base64,(.*)", data_url, re.DOTALL)
    if match:
        ext = match.group(1)
        b64_data = match.group(2)
    else:
        # Assume raw base64 PNG
        ext = "png"
        b64_data = data_url

    img_bytes = base64.b64decode(b64_data)
    # Ensure output path has correct extension
    if not output_path.lower().endswith(f".{ext}"):
        output_path = os.path.splitext(output_path)[0] + f".{ext}"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(img_bytes)
    return output_path


def parse_images_column(images_str: str) -> list:
    """Parse the semicolon-separated Images column into a list of filenames."""
    return [img.strip() for img in images_str.split(";") if img.strip()]


def load_progress(progress_file: str) -> set:
    """Load set of already-completed row indices from progress file."""
    done = set()
    if os.path.exists(progress_file):
        with open(progress_file, "r") as f:
            for line in f:
                line = line.strip()
                if line.isdigit():
                    done.add(int(line))
    return done


def save_progress(progress_file: str, row_idx: int):
    """Append a completed row index to the progress file."""
    with open(progress_file, "a") as f:
        f.write(f"{row_idx}\n")


# ──────────────────────────────────────────────────────────────────────────────
# SSH Tunnel helper
# ──────────────────────────────────────────────────────────────────────────────

def setup_ssh_tunnel(remote_host: str, remote_port: int, local_port: int):
    """
    Open an SSH tunnel: localhost:<local_port> -> remote_host:<remote_port>.
    Returns the subprocess.Popen object (caller should .terminate() when done).
    """
    cmd = [
        "ssh", "-N", "-L",
        f"{local_port}:localhost:{remote_port}",
        remote_host,
        "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=30",
    ]
    logger.info(f"Opening SSH tunnel: localhost:{local_port} -> {remote_host}:{remote_port}")
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    time.sleep(3)  # Give tunnel time to establish
    if proc.poll() is not None:
        stderr = proc.stderr.read().decode()
        raise RuntimeError(f"SSH tunnel failed to start: {stderr}")
    logger.info("SSH tunnel established.")
    return proc


# ──────────────────────────────────────────────────────────────────────────────
# Main batch logic
# ──────────────────────────────────────────────────────────────────────────────

def run_batch(
    csv_path: str,
    image_dir: str,
    output_dir: str,
    host: str = "localhost",
    port: int = 8001,
    num_inference_steps: int = 50,
    guidance_scale: float = 1.0,
    seed: int = 0,
    max_retries: int = 3,
    retry_delay: float = 5.0,
    start_row: int = 0,
    end_row: int = None,
):
    """
    Run batch image editing from a CSV file.

    Args:
        csv_path: Path to the input CSV.
        image_dir: Directory containing the source images.
        output_dir: Directory to save generated images.
        host: API host.
        port: API port.
        num_inference_steps: Diffusion steps.
        guidance_scale: Guidance scale.
        seed: Random seed.
        max_retries: Max retries per row on failure.
        retry_delay: Seconds to wait between retries.
        start_row: First data row index to process (0-based, excluding header).
        end_row: Last data row index (exclusive). None = process all.
    """
    os.makedirs(output_dir, exist_ok=True)
    progress_file = os.path.join(output_dir, ".progress")
    results_csv = os.path.join(output_dir, "results.csv")
    done = load_progress(progress_file)

    # Read CSV
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    total = len(rows)
    if end_row is not None:
        rows_to_process = rows[start_row:end_row]
    else:
        rows_to_process = rows[start_row:]

    logger.info(f"CSV loaded: {total} total rows, processing rows {start_row} to {start_row + len(rows_to_process) - 1}")
    logger.info(f"Already completed: {len(done)} rows")

    # Prepare results CSV (write header if new)
    write_header = not os.path.exists(results_csv)
    results_fp = open(results_csv, "a", newline="", encoding="utf-8")
    fieldnames = list(rows[0].keys()) + ["Output", "Status", "Error"]
    writer = csv.DictWriter(results_fp, fieldnames=fieldnames)
    if write_header:
        writer.writeheader()

    success_count = 0
    fail_count = 0

    for i, row in enumerate(rows_to_process):
        row_idx = start_row + i
        if row_idx in done:
            logger.info(f"[{row_idx+1}/{total}] Skipping (already done)")
            continue

        instruction = row.get("Instruction", "").strip()
        images_str = row.get("Images", "").strip()
        image_filenames = parse_images_column(images_str)

        logger.info(f"[{row_idx+1}/{total}] Processing: {instruction[:80]}...")
        logger.info(f"  Images: {image_filenames}")

        # Resolve image paths to data URLs
        image_data_urls = []
        missing = False
        for fname in image_filenames:
            fpath = os.path.join(image_dir, fname)
            if not os.path.exists(fpath):
                logger.error(f"  Image not found: {fpath}")
                missing = True
                break
            image_data_urls.append(image_to_data_url(fpath))

        if missing:
            result_row = dict(row)
            result_row["Output"] = ""
            result_row["Status"] = "ERROR"
            result_row["Error"] = f"Missing image file"
            writer.writerow(result_row)
            results_fp.flush()
            fail_count += 1
            save_progress(progress_file, row_idx)
            continue

        # Call API with retries
        output_filename = f"output_{row_idx:05d}.png"
        output_path = os.path.join(output_dir, output_filename)
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                result_data_url = call_qwen_image_edition(
                    images=image_data_urls,
                    prompt=instruction,
                    num_inference_steps=num_inference_steps,
                    guidance_scale=guidance_scale,
                    seed=seed,
                    host=host,
                    port=port,
                )
                saved_path = save_data_url_image(result_data_url, output_path)
                logger.info(f"  Saved: {saved_path}")

                result_row = dict(row)
                result_row["Output"] = os.path.basename(saved_path)
                result_row["Status"] = "OK"
                result_row["Error"] = ""
                writer.writerow(result_row)
                results_fp.flush()
                success_count += 1
                save_progress(progress_file, row_idx)
                last_error = None
                break

            except Exception as e:
                last_error = str(e)
                logger.warning(f"  Attempt {attempt}/{max_retries} failed: {last_error}")
                if attempt < max_retries:
                    time.sleep(retry_delay)

        if last_error is not None:
            logger.error(f"  FAILED after {max_retries} attempts: {last_error}")
            result_row = dict(row)
            result_row["Output"] = ""
            result_row["Status"] = "ERROR"
            result_row["Error"] = last_error
            writer.writerow(result_row)
            results_fp.flush()
            fail_count += 1
            save_progress(progress_file, row_idx)

    results_fp.close()
    logger.info(f"Batch complete. Success: {success_count}, Failed: {fail_count}")
    logger.info(f"Results CSV: {results_csv}")
    logger.info(f"Output images: {output_dir}")


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Batch image editing using Qwen model via ASG endpoint.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Direct connection (API already accessible):
  python script.py \\
      --csv workspace/MISSIONS/build_mm_train/mm_shopping_benchmark_train/samples.csv \\
      --image_dir workspace/MISSIONS/build_mm_train/mm_shopping_benchmark_train/images \\
      --output_dir workspace/MISSIONS/build_mm_train/mm_shopping_benchmark_train/output \\
      --host localhost --port 8001

  # Connect to remote ASG host (with SSH tunnel):
  python script.py \\
      --csv samples.csv --image_dir images/ --output_dir output/ \\
      --remote_host ec2-18-206-77-68.compute-1.amazonaws.com \\
      --remote_port 8001

  # Process a subset of rows:
  python script.py --csv samples.csv --image_dir images/ --output_dir output/ \\
      --start_row 100 --end_row 200
        """,
    )

    parser.add_argument("--csv", required=True, help="Path to input CSV file")
    parser.add_argument("--image_dir", required=True, help="Directory containing source images")
    parser.add_argument("--output_dir", required=True, help="Directory to save output images and results")

    # Connection
    parser.add_argument("--host", default="localhost", help="API host (default: localhost)")
    parser.add_argument("--port", type=int, default=8001, help="API port (default: 8001)")
    parser.add_argument("--remote_host", default=None,
                        help="Remote host for SSH tunnel (e.g. ec2-18-206-77-68.compute-1.amazonaws.com). "
                             "If set, an SSH tunnel is created automatically.")
    parser.add_argument("--remote_port", type=int, default=8001,
                        help="Remote port to tunnel to (default: 8001)")
    parser.add_argument("--local_port", type=int, default=8001,
                        help="Local port for the SSH tunnel (default: 8001)")

    # Model params
    parser.add_argument("--num_inference_steps", type=int, default=50)
    parser.add_argument("--guidance_scale", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=0)

    # Batch control
    parser.add_argument("--max_retries", type=int, default=3, help="Max retries per row (default: 3)")
    parser.add_argument("--retry_delay", type=float, default=5.0, help="Seconds between retries (default: 5)")
    parser.add_argument("--start_row", type=int, default=0, help="Start row index (0-based, default: 0)")
    parser.add_argument("--end_row", type=int, default=None, help="End row index (exclusive, default: all)")

    args = parser.parse_args()

    # Validate inputs
    if not os.path.exists(args.csv):
        logger.error(f"CSV file not found: {args.csv}")
        sys.exit(1)
    if not os.path.isdir(args.image_dir):
        logger.error(f"Image directory not found: {args.image_dir}")
        sys.exit(1)

    # SSH tunnel if needed
    tunnel_proc = None
    host = args.host
    port = args.port

    if args.remote_host:
        tunnel_proc = setup_ssh_tunnel(args.remote_host, args.remote_port, args.local_port)
        host = "localhost"
        port = args.local_port

    try:
        run_batch(
            csv_path=args.csv,
            image_dir=args.image_dir,
            output_dir=args.output_dir,
            host=host,
            port=port,
            num_inference_steps=args.num_inference_steps,
            guidance_scale=args.guidance_scale,
            seed=args.seed,
            max_retries=args.max_retries,
            retry_delay=args.retry_delay,
            start_row=args.start_row,
            end_row=args.end_row,
        )
    finally:
        if tunnel_proc:
            logger.info("Closing SSH tunnel...")
            tunnel_proc.terminate()
            tunnel_proc.wait()


if __name__ == "__main__":
    main()
