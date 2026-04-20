from __future__ import annotations

import base64
import io
import mimetypes
import re
from io import BytesIO
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen
from PIL import Image

_BASE64_RE = re.compile(r"^[A-Za-z0-9+/=\s]+$")
_PIL_FORMAT_TO_MIME = {
    "JPEG": "image/jpeg",
    "JPG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
    "GIF": "image/gif",
    "BMP": "image/bmp",
    "TIFF": "image/tiff",
}


def compose_system_prompt(
    system_prompt_loc="./workspace/SYSTEM_PROMPT.md",
    enabled_tools_loc="./workspace/TOOLS/enabled_tools.md",
    enabled_skills_loc="./workspace/SKILLS/enabled_skills.md",
    user_profile = None
):
    parts = []
    for path in (system_prompt_loc, enabled_tools_loc):
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read().strip()
        if text:
            parts.append(text)
        
    system_prompt = parts[0] + "\n# Tools Enabled\n" + parts[1]
    if user_profile: 
        system_prompt += ( "\n# User Profile\n" + user_profile )
    return system_prompt

def pil_to_base64(img: Image.Image, fmt: str = "PNG") -> str:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def base64_to_pil(b64: str) -> Image.Image:
    if b64.startswith("data:"):
        b64 = b64.split(",", 1)[1]
    raw = base64.b64decode(b64)
    return Image.open(BytesIO(raw))


def to_base64(
    src: str,
    *,
    timeout: int = 30,
    user_agent: str = "Mozilla/5.0",
    return_data_url: bool = True,
    default_mime: str = "image/png",
    max_image_size: Optional[int] = None,
) -> str:
    """
    Input: http(s) URL, local file path, data URL, or raw base64.
    Output:
      - if return_data_url=True: 'data:<mime>;base64,<...>'
      - else: raw base64 string (no 'data:' prefix)
    """
    if not isinstance(src, str) or not src.strip():
        raise ValueError("src must be a non-empty string")
    s = src.strip()

    def normalize_image_bytes(data: bytes, fallback: str) -> tuple[bytes, str]:
        try:
            with Image.open(BytesIO(data)) as img:
                image_format = (img.format or "").upper()
                mime = _PIL_FORMAT_TO_MIME.get(image_format, fallback)
                if not max_image_size or max(img.size) <= max_image_size:
                    return data, mime

                resized = resize_image_max(img, max_size=max_image_size)
                save_format = image_format or "PNG"
                if save_format in {"JPEG", "JPG"} and resized.mode not in {"RGB", "L"}:
                    resized = resized.convert("RGB")
                buf = BytesIO()
                resized.save(buf, format=save_format)
                return buf.getvalue(), mime
        except Exception:
            return data, fallback

    def wrap(b64: str, mime: str) -> str:
        b64 = b64.strip()
        return f"data:{mime};base64,{b64}" if return_data_url else b64

    # Case 1: data URL -> extract payload
    if s.lower().startswith("data:"):
        if ";base64," not in s.lower():
            raise ValueError("Only base64-encoded data URLs are supported (must contain ';base64,').")
        header, b64 = s.split(",", 1)
        header_mime = header.split(";")[0][5:] or default_mime
        raw = base64.b64decode(b64)
        raw, mime = normalize_image_bytes(raw, header_mime)
        b64 = base64.b64encode(raw).decode("utf-8")
        return wrap(b64, mime)

    # Case 2: http(s) URL -> download -> base64 encode
    if s.startswith("http://") or s.startswith("https://"):
        req = Request(s, headers={"User-Agent": user_agent})
        with urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            content_type = resp.headers.get("Content-Type", "").split(";")[0].strip()
        data, mime = normalize_image_bytes(data, content_type or default_mime)
        b64 = base64.b64encode(data).decode("utf-8")
        return wrap(b64, mime)

    # Case 3: local file path -> read -> base64 encode
    p = Path(s)
    if p.exists() and p.is_file():
        data = p.read_bytes()
        guessed_mime = mimetypes.guess_type(p.name)[0] or default_mime
        data, mime = normalize_image_bytes(data, guessed_mime)
        b64 = base64.b64encode(data).decode("utf-8")
        return wrap(b64, mime=mime)

    # Case 4: raw base64 -> accept as-is (best-effort validation)
    if _BASE64_RE.match(s) and len(s) % 4 == 0:
        raw = base64.b64decode(s)
        raw, mime = normalize_image_bytes(raw, default_mime)
        b64 = base64.b64encode(raw).decode("utf-8")
        return wrap(b64, mime)

    raise ValueError("Input image must be a data URL, http(s) URL, local file path, or raw base64.")


def resize_image_max(image: Image.Image, max_size: int = 512) -> Image.Image:
    width, height = image.size
    if width <= 0 or height <= 0:
        return image
    scale = max_size / max(width, height)
    if scale >= 1:
        return image
    new_size = (int(width * scale), int(height * scale))
    return image.resize(new_size)
