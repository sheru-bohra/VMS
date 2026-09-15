"""Generate invitation QR images for email."""

from __future__ import annotations

import base64
import io

import qrcode


def invitation_qr_png_base64(url: str) -> str:
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")
