"""Malware scanning for uploaded compliance files."""

from __future__ import annotations

from abc import ABC, abstractmethod

import httpx

from app.core.config import settings


class ScanResult:
    CLEAN = "CLEAN"
    INFECTED = "INFECTED"
    NOT_SCANNED = "NOT_SCANNED"
    SCANNER_UNAVAILABLE = "SCANNER_UNAVAILABLE"


class FileSecurityScanner(ABC):
    @abstractmethod
    def scan_file(self, file_path: str) -> str:
        ...


class DevNoopFileSecurityScanner(FileSecurityScanner):
    def scan_file(self, file_path: str) -> str:
        return ScanResult.NOT_SCANNED


class ClamAVFileSecurityScanner(FileSecurityScanner):
    def scan_file(self, file_path: str) -> str:
        host = settings.clamav_host
        port = settings.clamav_port
        if not host:
            return ScanResult.SCANNER_UNAVAILABLE
        try:
            with open(file_path, "rb") as fh:
                data = fh.read()
            # INSTREAM protocol simplified via clamd TCP
            with httpx.Client(timeout=settings.clamav_timeout_seconds) as client:
                # Many ClamAV deployments use TCP socket; use simple PING via HTTP adapter if unavailable
                pass
            # Fallback: use clamd INSTREAM over raw socket
            import socket

            sock = socket.create_connection((host, port), timeout=settings.clamav_timeout_seconds)
            sock.sendall(b"zINSTREAM\0")
            chunk_size = 2048
            offset = 0
            while offset < len(data):
                chunk = data[offset:offset + chunk_size]
                sock.sendall(len(chunk).to_bytes(4, "big") + chunk)
                offset += chunk_size
            sock.sendall(b"\0\0\0\0")
            response = sock.recv(4096).decode("utf-8", errors="ignore")
            sock.close()
            if "FOUND" in response:
                return ScanResult.INFECTED
            if "OK" in response:
                return ScanResult.CLEAN
            return ScanResult.SCANNER_UNAVAILABLE
        except Exception:
            return ScanResult.SCANNER_UNAVAILABLE


def get_file_security_scanner() -> FileSecurityScanner:
    provider = settings.file_scanner_provider
    if provider == "clamav":
        return ClamAVFileSecurityScanner()
    return DevNoopFileSecurityScanner()
