# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

"""Lab Streaming Layer bridge for the web version of OpenMATB.

Browsers cannot use LSL: the page sends the markers of the labstreaminglayer plugin to this program through a
WebSocket (web_lsl_bridge in config.ini), and it pushes them to an LSL stream, the same as the desktop version
("OpenMATB", type Markers), recorded with LabRecorder like any other stream.

usage:
    pip install pylsl
    python web/lsl_bridge.py                       # listens on ws://127.0.0.1:8766
    python web/lsl_bridge.py --port 8766 --origin https://lab.example.org

Run it on the computer of the participant (the page connects to 127.0.0.1). Timing: each marker carries its time in
the browser (the logtime of the session file, performance.now()). The bridge measures the offset between the browser
clock and the LSL clock like NTP: it sends its time, the page answers at once with its own time; the exchange with
the shortest round trip gives the offset, known to within half this round trip (typically < 1 ms). The markers are
stamped in LSL time with it, so the WebSocket and the browser loop add no delay to the recorded times.

Only the Python standard library and pylsl are used (no WebSocket package).
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import struct
import sys
from collections import deque
from typing import Any, Callable

DEFAULT_PORT: int = 8766
WEBSOCKET_GUID: str = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
# Same stream as the desktop version (plugins/labstreaminglayer.py)
STREAM_NAME: str = "OpenMATB"
STREAM_TYPE: str = "Markers"
STREAM_SOURCE_ID: str = "myuidw435368"
# Clock synchronization: a burst when the page connects, then one exchange per second
SYNC_BURST: int = 10
SYNC_BURST_INTERVAL: float = 0.05
SYNC_INTERVAL: float = 1.0
SYNC_WINDOW: int = 60  # The best of the last exchanges (the clocks drift slowly: keep a recent estimate)

OPCODE_TEXT, OPCODE_CLOSE, OPCODE_PING, OPCODE_PONG = 0x1, 0x8, 0x9, 0xA


# ── WebSocket (RFC 6455), server side ─────────────────────────────────────────


def accept_key(key: str) -> str:
    return base64.b64encode(hashlib.sha1((key + WEBSOCKET_GUID).encode("ascii")).digest()).decode("ascii")


def encode_frame(payload: bytes, opcode: int = OPCODE_TEXT) -> bytes:
    """A final, unmasked frame (servers do not mask)."""
    length: int = len(payload)
    if length < 126:
        header: bytes = struct.pack("!BB", 0x80 | opcode, length)
    elif length < 1 << 16:
        header = struct.pack("!BBH", 0x80 | opcode, 126, length)
    else:
        header = struct.pack("!BBQ", 0x80 | opcode, 127, length)
    return header + payload


async def read_frame(reader: asyncio.StreamReader) -> tuple[bool, int, bytes]:
    """(final, opcode, payload) of the next frame (clients mask their frames)."""
    first, second = await reader.readexactly(2)
    length: int = second & 0x7F
    if length == 126:
        (length,) = struct.unpack("!H", await reader.readexactly(2))
    elif length == 127:
        (length,) = struct.unpack("!Q", await reader.readexactly(8))
    mask: bytes = await reader.readexactly(4) if second & 0x80 else b"\0\0\0\0"
    data: bytes = await reader.readexactly(length)
    payload: bytes = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    return bool(first & 0x80), first & 0x0F, payload


async def read_request(reader: asyncio.StreamReader) -> tuple[str, dict[str, str]]:
    """The request line and the headers (lower case names) of an HTTP request."""
    lines: list[str] = (await reader.readuntil(b"\r\n\r\n")).decode("latin-1").split("\r\n")
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" in line:
            name, value = line.split(":", 1)
            headers[name.strip().lower()] = value.strip()
    return lines[0], headers


# ── Clock synchronization ─────────────────────────────────────────────────────


class ClockSync:
    """Offset between the browser clock and the LSL clock (browser - LSL, seconds), from NTP-like exchanges:
    sent at t0, the browser time b is read around the middle of the round trip, received at t1 (LSL times)."""

    def __init__(self, window: int = SYNC_WINDOW) -> None:
        self.samples: deque[tuple[float, float]] = deque(maxlen=window)  # (round trip, offset)

    def add(self, t0: float, browser: float, t1: float) -> None:
        self.samples.append((t1 - t0, browser - (t0 + t1) / 2))

    def best(self) -> tuple[float, float] | None:
        """(round trip, offset) of the exchange with the shortest round trip, or None."""
        return min(self.samples) if self.samples else None

    def to_lsl(self, browser_time: float) -> float | None:
        best = self.best()
        return None if best is None else browser_time - best[1]


# ── Bridge ────────────────────────────────────────────────────────────────────


class Bridge:
    """Receives the pages (WebSocket) and pushes their markers to one LSL outlet.

    outlet: push_sample([value], timestamp); clock: the LSL clock (pylsl.local_clock), both replaced in tests."""

    def __init__(
        self,
        outlet: Any,
        clock: Callable[[], float],
        origins: list[str] | None = None,
        log: Callable[[str], None] = print,
    ) -> None:
        self.outlet = outlet
        self.clock = clock
        self.origins = origins or []
        self.log = log
        self.sync = ClockSync()  # Shared by the connections: same computer, same clocks
        self.markers: int = 0

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            _, headers = await read_request(reader)
            if headers.get("upgrade", "").lower() != "websocket" or "sec-websocket-key" not in headers:
                # A plain HTTP request (e.g. opened in a browser to check that the bridge runs)
                body: bytes = f"OpenMATB LSL bridge: {self.markers} markers pushed\n".encode()
                writer.write(
                    b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nAccess-Control-Allow-Origin: *\r\n"
                    + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                    + body
                )
                await writer.drain()
                return
            origin: str = headers.get("origin", "")
            if self.origins and origin not in self.origins:
                self.log(f"Refused a page from {origin or 'an unknown origin'} (--origin)")
                writer.write(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                await writer.drain()
                return
            writer.write(
                b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                + f"Sec-WebSocket-Accept: {accept_key(headers['sec-websocket-key'])}\r\n\r\n".encode()
            )
            await writer.drain()
            self.log(f"Page connected ({origin or 'unknown origin'})")
            await self.session(reader, writer)
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            writer.close()

    async def session(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        sent: dict[int, float] = {}  # Sync exchange id -> LSL time when sent

        def send(message: dict) -> None:
            writer.write(encode_frame(json.dumps(message).encode()))

        async def sync_loop() -> None:
            exchange: int = 0
            while True:
                exchange += 1
                sent[exchange] = self.clock()
                send({"type": "sync", "id": exchange})
                await writer.drain()
                await asyncio.sleep(SYNC_BURST_INTERVAL if exchange < SYNC_BURST else SYNC_INTERVAL)

        syncing = asyncio.ensure_future(sync_loop())
        fragments: bytes = b""
        try:
            while True:
                final, opcode, payload = await read_frame(reader)
                received: float = self.clock()
                if opcode == OPCODE_CLOSE:
                    writer.write(encode_frame(payload[:2], OPCODE_CLOSE))
                    break
                if opcode == OPCODE_PING:
                    writer.write(encode_frame(payload, OPCODE_PONG))
                    continue
                if opcode not in (OPCODE_TEXT, 0x0):  # Text and continuation frames only
                    continue
                fragments += payload
                if not final:
                    continue
                message: dict = json.loads(fragments.decode("utf-8"))
                fragments = b""
                if message.get("type") == "sync" and message.get("id") in sent:
                    self.sync.add(sent.pop(message["id"]), float(message["browser"]), received)
                    rtt, offset = self.sync.best()
                    send({"type": "offset", "offset": offset, "rtt": rtt})
                elif message.get("type") == "marker":
                    self.push(str(message["value"]), message.get("time"), received)
        finally:
            syncing.cancel()
            self.log(f"Page disconnected ({self.markers} markers pushed)")

    def push(self, value: str, browser_time: float | None, received: float) -> None:
        """Stamp the marker in LSL time from its browser time (its reception time if the offset is not known)."""
        timestamp: float | None = self.sync.to_lsl(float(browser_time)) if browser_time is not None else None
        self.outlet.push_sample([value], timestamp if timestamp is not None else received)
        self.markers += 1


def create_outlet() -> tuple[Any, Callable[[], float]]:
    try:
        import pylsl
    except ImportError:
        sys.exit("pylsl is missing: pip install pylsl")
    info = pylsl.StreamInfo(STREAM_NAME, STREAM_TYPE, 1, 0, "string", STREAM_SOURCE_ID)
    return pylsl.StreamOutlet(info), pylsl.local_clock


async def serve(bridge: Bridge, host: str, port: int) -> None:
    server = await asyncio.start_server(bridge.handle, host, port)
    bridge.log(f"OpenMATB LSL bridge: ws://{host}:{port} -> LSL stream {STREAM_NAME!r} ({STREAM_TYPE})")
    bridge.log("Set web_lsl_bridge in config.ini to this address. Ctrl+C to stop.")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1", help="address to listen on (default: this computer only)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--origin",
        action="append",
        default=[],
        help="only accept the pages of this site, e.g. https://lab.example.org (repeatable; default: any)",
    )
    args = parser.parse_args()
    outlet, clock = create_outlet()
    try:
        asyncio.run(serve(Bridge(outlet, clock, args.origin), args.host, args.port))
    except KeyboardInterrupt:
        pass
