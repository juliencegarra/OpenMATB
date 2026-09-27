// Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
// Institut National Universitaire Champollion (Albi, France).
// License : CeCILL, version 2.1 (see the LICENSE file)

// USB trigger box for the parallelport plugin (web_serial_trigger=True in config.ini), with the Web Serial API
// (Chrome and Edge): each value of the plugin is written as one byte to a serial port, which the box outputs on its
// 8 lines until the next value, as a parallel port does (Brain Products TriggerBox, BioSemi USB trigger interface,
// Neurospec MMBT-S, an Arduino...). The port is chosen once on the start page; the browser remembers the permission.
// core/platform.py calls write() from Python (window.openmatbSerialTrigger).

// Name of the port on the start page: USB vendor and product IDs (the browser does not give the device name)
export function describePort(port) {
    const { usbVendorId, usbProductId } = port.getInfo();
    const hex = (id) => id.toString(16).padStart(4, "0");
    return usbVendorId === undefined ? "serial port" : `USB ${hex(usbVendorId)}:${hex(usbProductId)}`;
}

export class SerialTrigger {
    constructor(serial = navigator.serial, now = () => performance.now()) {
        this.serial = serial;
        this.now = now;
        this.port = null;
        this.writer = null;
        this.queue = Promise.resolve();
        this.nextWriteAt = 0; // performance.now() before which the value written last must stay
        this.written = 0;
        this.errors = [];
    }

    static supported(serial = navigator.serial) {
        return Boolean(serial);
    }

    // The port allowed in a previous visit (when there is only one), or null
    async restore() {
        const ports = await this.serial.getPorts();
        this.port = ports.length === 1 ? ports[0] : this.port;
        return this.port;
    }

    // Asks the participant (or the experimenter) to choose the port: must be called from a click
    async choose() {
        this.port = await this.serial.requestPort();
        return this.port;
    }

    async open(baudRate) {
        if (this.writer) {
            return; // Already opened by a start refused for another reason
        }
        if (!this.port.writable) {
            await this.port.open({ baudRate });
        }
        this.writer = this.port.writable.getWriter();
    }

    // Writes the value (0-255) at once, unless the previous value must still be held: holdMs is how long this value
    // stays before the next one (the delayms of the plugin). The Python loop runs every 8 to 16 ms in the browser:
    // the value and the reset of a 5 ms trigger may come in the same update, they must not be written together.
    // The hold is counted from the real write: Python runs in the same thread as the writes, which may come late.
    write(value, holdMs = 0) {
        this.queue = this.queue.then(async () => {
            const delay = this.nextWriteAt - this.now();
            if (delay > 0) {
                await new Promise((resolve) => setTimeout(resolve, delay));
            }
            this.nextWriteAt = this.now() + holdMs;
            try {
                await this.writer.write(Uint8Array.of(value & 0xff));
                this.written += 1;
            } catch (error) {
                this.errors.push(String(error.message || error));
                console.error(`[OpenMATB] Trigger ${value} not written:`, error);
            }
        });
    }

    // End of the session: the last writes, then the port is released
    async close() {
        await this.queue;
        try {
            this.writer?.releaseLock();
            await this.port?.close();
        } catch (error) {
            console.warn("[OpenMATB] Serial port not closed:", error);
        }
    }
}
