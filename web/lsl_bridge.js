// Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
// Institut National Universitaire Champollion (Albi, France).
// License : CeCILL, version 2.1 (see the LICENSE file)

// Lab Streaming Layer from the browser (web_lsl_bridge in config.ini): browsers cannot use LSL, so the markers of the
// labstreaminglayer plugin go through a WebSocket to web/lsl_bridge.py, run on the recording computer, which
// creates the same "OpenMATB" marker stream as the desktop version.
// Clocks: each marker carries its browser time (performance.now(), the logtime of the session file). The bridge
// measures the offset between this clock and the LSL clock (it sends its time, the page answers at once with its
// own: NTP-like, the exchange with the shortest round trip wins) and stamps the marker in LSL time.
// core/platform.py calls push() from Python (window.openmatbLsl).

export const DEFAULT_BRIDGE_URL = "ws://127.0.0.1:8766";
const CONNECT_TIMEOUT_MS = 5000;
const RECONNECT_MS = 2000;

export class LslBridge {
    constructor(url, { WebSocketImpl = WebSocket, now = () => performance.now() } = {}) {
        this.url = url;
        this.WebSocket = WebSocketImpl;
        this.now = now;
        this.socket = null;
        this.queue = []; // Markers not sent yet (bridge disconnected): sent with their time when it is back
        this.offset = null; // Browser time - LSL time (s), measured by the bridge
        this.rtt = null; // Round trip of the measure (s): the offset is known to within rtt / 2
        this.sent = 0;
        this.closed = false;
    }

    // Resolves once the bridge has measured the clock offset; rejects if it cannot be reached
    connect() {
        return new Promise((resolve, reject) => {
            const fail = () => {
                clearTimeout(timeout);
                this.socket?.close();
                reject(new Error(`the LSL bridge does not answer at ${this.url}: start python web/lsl_bridge.py`));
            };
            const timeout = setTimeout(fail, CONNECT_TIMEOUT_MS);
            this.open(() => {
                clearTimeout(timeout);
                resolve();
            }, fail);
        });
    }

    open(onReady = () => {}, onFail = () => {}) {
        const socket = new this.WebSocket(this.url);
        this.socket = socket;
        socket.onopen = () => socket.send(JSON.stringify({ type: "hello", client: "OpenMATB" }));
        socket.onmessage = (event) => {
            const message = JSON.parse(event.data);
            if (message.type === "sync") {
                // Answered at once: the bridge measures the round trip
                socket.send(JSON.stringify({ type: "sync", id: message.id, browser: this.now() / 1000 }));
            } else if (message.type === "offset") {
                const first = this.offset === null;
                this.offset = message.offset;
                this.rtt = message.rtt;
                this.flush();
                if (first) {
                    onReady();
                }
            }
        };
        socket.onclose = () => {
            if (this.offset === null) {
                onFail(); // Not reachable (connection refused)
            } else if (!this.closed) {
                console.warn(`[OpenMATB] LSL bridge disconnected, reconnecting (${this.queue.length} markers kept)`);
                setTimeout(() => this.open(), RECONNECT_MS);
            }
        };
    }

    get connected() {
        return this.socket?.readyState === this.WebSocket.OPEN;
    }

    // time: browser time of the marker (s); now if not given
    push(value, time = this.now() / 1000) {
        this.queue.push({ type: "marker", value: String(value), time });
        this.flush();
    }

    flush() {
        while (this.connected && this.queue.length) {
            this.socket.send(JSON.stringify(this.queue.shift()));
            this.sent += 1;
        }
    }

    close() {
        this.closed = true;
        this.flush();
        this.socket?.close();
    }
}
