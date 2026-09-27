"""Tests for web/lsl_bridge.py: the WebSocket server that pushes the markers of the web version to LSL."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import struct
from pathlib import Path

import pytest

ROOT: Path = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def bridge_module():
    spec = importlib.util.spec_from_file_location("lsl_bridge", ROOT / "web" / "lsl_bridge.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeOutlet:
    def __init__(self) -> None:
        self.samples: list[tuple[list[str], float]] = []

    def push_sample(self, sample: list[str], timestamp: float) -> None:
        self.samples.append((sample, timestamp))


class FakeClock:
    """The LSL clock: advances by `step` at each reading."""

    def __init__(self, start: float = 5000.0, step: float = 0.0005) -> None:
        self.time = start
        self.step = step

    def __call__(self) -> float:
        self.time += self.step
        return self.time


def client_frame(payload: bytes, opcode: int = 0x1, final: bool = True) -> bytes:
    """A masked frame, as browsers send them."""
    mask = os.urandom(4)
    length = len(payload)
    first = (0x80 if final else 0) | opcode
    if length < 126:
        header = struct.pack("!BB", first, 0x80 | length)
    elif length < 1 << 16:
        header = struct.pack("!BBH", first, 0x80 | 126, length)
    else:
        header = struct.pack("!BBQ", first, 0x80 | 127, length)
    return header + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload))


class TestWebSocket:
    def test_accept_key(self, bridge_module):
        # The example of RFC 6455
        assert bridge_module.accept_key("dGhlIHNhbXBsZSBub25jZQ==") == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="

    @pytest.mark.parametrize("length", [0, 125, 126, 65535, 65536])
    def test_masked_frames_are_read(self, bridge_module, length):
        payload = bytes(i % 251 for i in range(length))

        async def read():
            reader = asyncio.StreamReader()
            reader.feed_data(client_frame(payload))
            return await bridge_module.read_frame(reader)

        assert asyncio.run(read()) == (True, 0x1, payload)

    @pytest.mark.parametrize("length", [5, 126, 70000])
    def test_server_frames_are_not_masked(self, bridge_module, length):
        frame = bridge_module.encode_frame(b"x" * length)
        assert frame[0] == 0x81 and not frame[1] & 0x80
        assert frame.endswith(b"x" * length)


class TestClockSync:
    def test_the_shortest_round_trip_wins(self, bridge_module):
        sync = bridge_module.ClockSync()
        assert sync.best() is None and sync.to_lsl(1.0) is None
        # LSL clock = browser clock - 100 s. Exchange 1: 10 ms round trip, the page answered late (offset error)
        sync.add(t0=1000.000, browser=1100.008, t1=1000.010)
        # Exchange 2: 1 ms round trip, answered in the middle
        sync.add(t0=1001.000, browser=1101.0005, t1=1001.001)
        rtt, offset = sync.best()
        assert rtt == pytest.approx(0.001) and offset == pytest.approx(100.0)
        assert sync.to_lsl(1102.25) == pytest.approx(1002.25)

    def test_old_exchanges_are_forgotten(self, bridge_module):
        sync = bridge_module.ClockSync(window=3)
        sync.add(0.0, 10.0, 0.0001)  # Best, but old
        for i in range(3):
            sync.add(1.0 + i, 11.0 + i + 0.001, 1.002 + i)
        assert sync.best()[0] == pytest.approx(0.002)


async def _connect(port: int, origin: str = "http://127.0.0.1:8000"):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(
        (
            "GET / HTTP/1.1\r\nHost: 127.0.0.1\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\nOrigin: {origin}\r\n\r\n"
        ).encode()
    )
    status = (await reader.readuntil(b"\r\n\r\n")).decode()
    return reader, writer, status


async def _message(module, reader) -> dict:
    _, _, payload = await module.read_frame(reader)  # Server frames are not masked: read_frame reads them too
    return json.loads(payload)


def _send(writer, message: dict) -> None:
    writer.write(client_frame(json.dumps(message).encode()))


class TestBridge:
    def run(self, bridge_module, scenario, origins=None):
        outlet, clock, logs = FakeOutlet(), FakeClock(), []
        bridge = bridge_module.Bridge(outlet, clock, origins, log=logs.append)

        async def main():
            server = await asyncio.start_server(bridge.handle, "127.0.0.1", 0)
            port = server.sockets[0].getsockname()[1]
            async with server:
                result = await asyncio.wait_for(scenario(port), timeout=10)
            return result

        return asyncio.run(main()), outlet, clock, logs

    def test_markers_are_stamped_in_lsl_time(self, bridge_module):
        """The page answers the sync messages with its clock (LSL time + 250 s here): markers are converted."""

        async def scenario(port):
            reader, writer, status = await _connect(port)
            offsets = []
            for _ in range(3):
                sync = await _message(bridge_module, reader)
                assert sync["type"] == "sync"
                _send(writer, {"type": "sync", "id": sync["id"], "browser": clock.time + 250.0})
                offsets.append(await _message(bridge_module, reader))
            _send(writer, {"type": "marker", "value": "sysmon;failure", "time": 7000.125})
            writer.write(client_frame(b"\x03\xe8", opcode=0x8))
            closing = await bridge_module.read_frame(reader)
            writer.close()
            return status, offsets, closing

        clock = FakeClock()
        outlet, logs = FakeOutlet(), []
        bridge = bridge_module.Bridge(outlet, clock, log=logs.append)

        async def main():
            server = await asyncio.start_server(bridge.handle, "127.0.0.1", 0)
            async with server:
                return await asyncio.wait_for(scenario(server.sockets[0].getsockname()[1]), timeout=10)

        status, offsets, closing = asyncio.run(main())
        assert status.startswith("HTTP/1.1 101")
        assert "Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=" in status
        # The page answered right after the clock reading of the sending: offset 250 s, within the round trip
        assert offsets[-1]["type"] == "offset"
        assert offsets[-1]["offset"] == pytest.approx(250.0, abs=offsets[-1]["rtt"])
        [(sample, timestamp)] = outlet.samples
        assert sample == ["sysmon;failure"]
        assert timestamp == pytest.approx(7000.125 - offsets[-1]["offset"])
        assert closing[1] == 0x8
        assert bridge.markers == 1
        assert any("Page connected" in line for line in logs)

    def test_marker_before_the_first_sync(self, bridge_module):
        """No offset yet: the marker is stamped when it is received."""

        async def scenario(port):
            reader, writer, _ = await _connect(port)
            _send(writer, {"type": "marker", "value": "early", "time": 1.0})
            writer.write(client_frame(b"", opcode=0x8))
            await bridge_module.read_frame(reader)  # Sync message
            writer.close()

        _, outlet, clock, _ = self.run(bridge_module, scenario)
        [(sample, timestamp)] = outlet.samples
        assert sample == ["early"] and 5000 < timestamp <= clock.time

    def test_fragmented_message_and_ping(self, bridge_module):
        async def scenario(port):
            reader, writer, _ = await _connect(port)
            text = json.dumps({"type": "marker", "value": "é" * 100, "time": None}).encode()
            writer.write(client_frame(text[:50], final=False))
            writer.write(client_frame(b"hi", opcode=0x9))  # Ping between the fragments
            writer.write(client_frame(text[50:], opcode=0x0))
            frames = [await bridge_module.read_frame(reader) for _ in range(2)]
            writer.write(client_frame(b"", opcode=0x8))
            await asyncio.sleep(0.05)
            writer.close()
            return frames

        frames, outlet, _, _ = self.run(bridge_module, scenario)
        assert (True, 0xA, b"hi") in frames  # Pong
        assert outlet.samples[0][0] == ["é" * 100]

    def test_origin_not_allowed(self, bridge_module):
        async def scenario(port):
            _, writer, status = await _connect(port, origin="https://other.example.org")
            writer.close()
            return status

        status, _, _, logs = self.run(bridge_module, scenario, origins=["https://lab.example.org"])
        assert status.startswith("HTTP/1.1 403")
        assert any("Refused" in line for line in logs)

    def test_plain_http_request_says_the_bridge_runs(self, bridge_module):
        async def scenario(port):
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.write(b"GET / HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
            response = await reader.read()
            writer.close()
            return response.decode()

        response, _, _, _ = self.run(bridge_module, scenario)
        assert response.startswith("HTTP/1.1 200") and "OpenMATB LSL bridge: 0 markers pushed" in response
