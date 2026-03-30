#!/usr/bin/env python3
"""
MM Shopping Benchmark Dataset Editor — Backend Server
Serves the editor UI, images, and handles CRUD operations on samples.csv
"""

import csv
import io
import json
import os
import shutil
import sys
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

PORT = 8765
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, 'samples.csv')
IMAGES_DIR = os.path.join(BASE_DIR, 'images')
BACKUP_DIR = os.path.join(BASE_DIR, 'backups')

FIELDNAMES = ['Type', 'Benchmark', 'Task', 'Instruction', 'Images']



def normalize_images(raw):
    """Parse Images field: supports both JSON array and semicolon-separated."""
    if not raw or not raw.strip():
        return ''
    s = raw.strip()
    if s.startswith('['):
        try:
            imgs = json.loads(s)
            return '; '.join(img.strip() for img in imgs if img.strip())
        except (json.JSONDecodeError, TypeError):
            pass
    return s

def read_csv():
    rows = []
    with open(CSV_PATH, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row['Images'] = normalize_images(row.get('Images', ''))
            rows.append(row)
    return rows


def write_csv(rows):
    # Create backup first
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(BACKUP_DIR, f'samples_{ts}.csv')
    shutil.copy2(CSV_PATH, backup_path)
    # Keep only last 50 backups
    backups = sorted(os.listdir(BACKUP_DIR))
    while len(backups) > 50:
        os.remove(os.path.join(BACKUP_DIR, backups.pop(0)))
    # Write new CSV
    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def list_all_images():
    if not os.path.isdir(IMAGES_DIR):
        return []
    return sorted([f for f in os.listdir(IMAGES_DIR)
                    if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif'))])


class EditorHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/' or path == '/editor':
            self.serve_file('editor.html', 'text/html')
        elif path == '/api/samples':
            rows = read_csv()
            self.json_response(rows)
        elif path == '/api/images':
            images = list_all_images()
            self.json_response(images)
        elif path.startswith('/images/'):
            # Serve image files
            self.directory = BASE_DIR
            self.path = path
            super().do_GET()
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self.read_body()

        if path == '/api/samples/save':
            # Full dataset save
            data = json.loads(body)
            rows = data.get('samples', [])
            # Validate
            for r in rows:
                for f in FIELDNAMES:
                    if f not in r:
                        r[f] = ''
            write_csv(rows)
            self.json_response({'ok': True, 'count': len(rows)})

        elif path == '/api/samples/update':
            # Update single sample by index
            data = json.loads(body)
            idx = data['index']
            sample = data['sample']
            rows = read_csv()
            if 0 <= idx < len(rows):
                for f in FIELDNAMES:
                    if f in sample:
                        rows[idx][f] = sample[f]
                write_csv(rows)
                self.json_response({'ok': True})
            else:
                self.json_response({'ok': False, 'error': 'Index out of range'}, 400)

        elif path == '/api/samples/delete':
            data = json.loads(body)
            indices = sorted(data['indices'], reverse=True)
            rows = read_csv()
            for idx in indices:
                if 0 <= idx < len(rows):
                    rows.pop(idx)
            write_csv(rows)
            self.json_response({'ok': True, 'count': len(rows)})

        elif path == '/api/samples/add':
            data = json.loads(body)
            sample = data['sample']
            insert_at = data.get('insertAt', None)
            rows = read_csv()
            new_row = {f: sample.get(f, '') for f in FIELDNAMES}
            if insert_at is not None and 0 <= insert_at <= len(rows):
                rows.insert(insert_at, new_row)
            else:
                rows.append(new_row)
            write_csv(rows)
            self.json_response({'ok': True, 'count': len(rows)})

        elif path == '/api/samples/reorder':
            data = json.loads(body)
            old_idx = data['from']
            new_idx = data['to']
            rows = read_csv()
            if 0 <= old_idx < len(rows) and 0 <= new_idx < len(rows):
                item = rows.pop(old_idx)
                rows.insert(new_idx, item)
                write_csv(rows)
                self.json_response({'ok': True})
            else:
                self.json_response({'ok': False, 'error': 'Index out of range'}, 400)

        elif path == '/api/samples/duplicate':
            data = json.loads(body)
            idx = data['index']
            rows = read_csv()
            if 0 <= idx < len(rows):
                new_row = dict(rows[idx])
                rows.insert(idx + 1, new_row)
                write_csv(rows)
                self.json_response({'ok': True, 'count': len(rows)})
            else:
                self.json_response({'ok': False, 'error': 'Index out of range'}, 400)

        else:
            self.send_error(404)

    def read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        return self.rfile.read(length).decode('utf-8')

    def json_response(self, data, code=200):
        body = json.dumps(data).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def serve_file(self, filename, content_type):
        filepath = os.path.join(BASE_DIR, filename)
        if not os.path.exists(filepath):
            self.send_error(404)
            return
        with open(filepath, 'rb') as f:
            body = f.read()
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        if '/api/' in str(args[0]) if args else False:
            super().log_message(format, *args)


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    os.chdir(BASE_DIR)
    server = HTTPServer(('0.0.0.0', port), EditorHandler)
    print(f'🛒 MM Shopping Benchmark Editor running at http://localhost:{port}')
    print(f'   CSV: {CSV_PATH}')
    print(f'   Images: {IMAGES_DIR} ({len(list_all_images())} files)')
    print(f'   Press Ctrl+C to stop')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down...')
        server.shutdown()
