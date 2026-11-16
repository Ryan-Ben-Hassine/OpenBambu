"""
Own your bambu Cloud - Bambu Lab Live Camera Streamer
Connects to Bambu Lab Camera on port 6000 (TLS) or RTSP,
and provides live MJPEG streaming + snapshot capture.
Zero external binaries required for core TLS capture.
Copyright (c) 2026 Ryan Ben Hassine (ryanbenhassine).
"""

import ssl
import time
import socket
import struct
import threading
from typing import Optional, Dict

class CameraStreamer:
    def __init__(self, ip: str, access_code: str, port: int = 6000):
        self.ip = ip
        self.access_code = access_code
        self.port = port
        self.running = False
        self.connected = False
        self.latest_frame: Optional[bytes] = None
        self.last_frame_time: float = 0
        self.lock = threading.Lock()
        self.new_frame_event = threading.Event()
        self.worker_thread: Optional[threading.Thread] = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.worker_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.worker_thread.start()

    def stop(self):
        self.running = False
        self.connected = False

    def update_credentials(self, ip: str, access_code: str):
        with self.lock:
            if self.ip != ip or self.access_code != access_code:
                self.ip = ip
                self.access_code = access_code
                self.connected = False

    def _recv_exact(self, conn: socket.socket, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n and self.running:
            c = conn.recv(n - len(buf))
            if not c:
                raise EOFError("Socket closed")
            buf.extend(c)
        return bytes(buf)

    def _capture_loop(self):
        while self.running:
            conn = None
            try:
                # 80-byte Bambu authentication handshake
                header = struct.pack("<IIII", 0x40, 0x3000, 0, 0)
                username = b"bblp".ljust(32, b"\x00")
                password = self.access_code.encode("ascii").ljust(32, b"\x00")
                auth_packet = header + username + password

                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE

                raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                raw_sock.settimeout(5.0)
                conn = ctx.wrap_socket(raw_sock, server_hostname=self.ip)
                conn.connect((self.ip, self.port))
                conn.sendall(auth_packet)

                self.connected = True
                conn.settimeout(4.0)

                while self.running:
                    # 16-byte frame header: <IIII (magic, payload_len, ...)
                    hdr_data = self._recv_exact(conn, 16)
                    _, payload_len, _, _ = struct.unpack("<IIII", hdr_data)

                    if payload_len <= 0 or payload_len > 5_000_000:
                        continue

                    frame_bytes = self._recv_exact(conn, payload_len)
                    # Verify JPEG SOI (0xFFD8) and EOI (0xFFD9)
                    if len(frame_bytes) > 4 and frame_bytes.startswith(b"\xff\xd8") and frame_bytes.endswith(b"\xff\xd9"):
                        with self.lock:
                            self.latest_frame = frame_bytes
                            self.last_frame_time = time.time()
                        self.new_frame_event.set()
                        self.new_frame_event.clear()
            except Exception:
                self.connected = False
                time.sleep(2.0)
            finally:
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass

    def get_snapshot(self) -> Optional[bytes]:
        with self.lock:
            # If we have a fresh frame within last 5 seconds, return it
            if self.latest_frame and (time.time() - self.last_frame_time < 5.0):
                return self.latest_frame
        
        # Check host gateway fallback (if local camera proxy is active)
        import urllib.request
        for fallback_url in ["http://127.0.0.1:9910/snapshot.jpg", "http://172.18.0.1:9910/snapshot.jpg"]:
            try:
                req = urllib.request.Request(fallback_url)
                with urllib.request.urlopen(req, timeout=1.5) as resp:
                    if resp.status == 200:
                        data = resp.read()
                        with self.lock:
                            self.latest_frame = data
                            self.last_frame_time = time.time()
                        return data
            except Exception:
                continue

        with self.lock:
            return self.latest_frame

class MultiCameraManager:
    def __init__(self, json_store):
        self.store = json_store
        self.streamers: Dict[str, CameraStreamer] = {}
        self.lock = threading.Lock()

    def get_streamer(self, printer_id: str) -> Optional[CameraStreamer]:
        with self.lock:
            if printer_id not in self.streamers:
                printer = self.store.get_printer(printer_id)
                if not printer:
                    return None
                s = CameraStreamer(
                    ip=printer.get("ip", ""),
                    access_code=printer.get("access_code", ""),
                    port=int(printer.get("camera_port", 6000))
                )
                s.start()
                self.streamers[printer_id] = s
            return self.streamers[printer_id]
