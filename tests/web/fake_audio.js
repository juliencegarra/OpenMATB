// Silent Web Audio stand-in, installed by tests/web/conftest.py only when the browser has no AudioContext
// (Playwright's WebKit build for Windows has no Web Audio; Safari itself has it). pyglet creates its
// audio driver when pyglet.media is imported, so without it OpenMATB could not be tested at all.
if (!("AudioContext" in window)) {
    window.__openmatbFakeAudio = true;

    const param = () => ({ value: 0, setValueAtTime() {}, linearRampToValueAtTime() {}, setTargetAtTime() {} });
    const node = () => ({
        connect() {},
        disconnect() {},
        gain: param(),
        playbackRate: param(),
        positionX: param(), positionY: param(), positionZ: param(),
        orientationX: param(), orientationY: param(), orientationZ: param(),
        forwardX: param(), forwardY: param(), forwardZ: param(),
        upX: param(), upY: param(), upZ: param(),
    });

    class FakeAudioContext {
        constructor() {
            this.state = "running";
            this.currentTime = 0;
            this.onstatechange = null;
            this.destination = node();
            this.listener = node();
        }

        resume() { return Promise.resolve(); }
        createGain() { return node(); }
        createPanner() { return node(); }

        createBufferSource() {
            const listeners = [];
            return Object.assign(node(), {
                buffer: null,
                loop: false,
                onended: null,
                addEventListener(type, listener) { if (type === "ended") listeners.push(listener); },
                removeEventListener() {},
                start() {
                    // Ends after the (fake) buffer duration, like a real source
                    setTimeout(() => {
                        this.onended?.({});
                        listeners.forEach((listener) => listener({}));
                    }, (this.buffer?.duration ?? 0) * 1000);
                },
                stop() {},
            });
        }

        decodeAudioData() {
            const buffer = { duration: 0.5, length: 22050, sampleRate: 44100, numberOfChannels: 1,
                getChannelData: () => new Float32Array(22050) };
            return Promise.resolve(buffer);
        }
    }

    window.AudioContext = FakeAudioContext;
}
