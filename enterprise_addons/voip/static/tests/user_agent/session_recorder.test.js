import { advanceTime, describe, expect, test } from "@odoo/hoot";
import { SessionRecorder } from "@voip/core/web/session_recorder";
import { patchWithCleanup } from "@web/../tests/web_test_helpers";

describe.current.tags("headless");

function makeTrack(name) {
    return {
        kind: "audio",
        readyState: "live",
        name,
        stop() {
            expect.step(`stop:${name}`);
        },
    };
}

function patchWebAudio(supportedMimeType) {
    class FakeAudioNode {
        constructor() {
            this.connections = new Set();
        }
        connect(target) {
            this.connections.add(target);
            expect.step(`connect:${this.constructor.name}->${target.constructor.name}`);
        }
        disconnect() {
            this.connections.clear();
            expect.step(`disconnect:${this.constructor.name}`);
        }
    }

    class MediaStreamAudioDestinationNode extends FakeAudioNode {
        constructor() {
            super();
            this.stream = { type: "MediaStream" };
        }
    }

    class MediaStreamSourceNode extends FakeAudioNode {
        constructor(stream) {
            super();
            this.trackName = stream.getAudioTracks()[0].name;
        }
        connect(target) {
            super.connect(target);
            expect.step(`wire:${this.trackName}->${target.constructor.name}`);
        }
    }

    class GainNode extends FakeAudioNode {}

    class FakeAudioContext {
        constructor() {
            this.state = "running";
        }
        createMediaStreamSource(stream) {
            return new MediaStreamSourceNode(stream);
        }
        close() {
            this.state = "closed";
            expect.step("audio-context:close");
            return Promise.resolve();
        }
    }

    class FakeMediaRecorder extends EventTarget {
        constructor(stream, options) {
            super();
            this.stream = stream;
            this.options = options;
            this.mimeType = options.mimeType;
            this.state = "inactive";
        }
        static isTypeSupported(type) {
            return !supportedMimeType || type === supportedMimeType;
        }
        start() {
            this.state = "recording";
            expect.step("recorder:start");
        }
        stop() {
            this.state = "inactive";
            expect.step("recorder:stop");
            this.dispatchEvent(
                Object.assign(new Event("dataavailable"), {
                    data: new Blob(["audio"], { type: this.mimeType }),
                })
            );
            this.dispatchEvent(new Event("stop"));
        }
    }

    patchWithCleanup(window, {
        AudioContext: FakeAudioContext,
        MediaStreamAudioDestinationNode,
        GainNode,
        MediaRecorder: FakeMediaRecorder,
        MediaStream: class {
            constructor(tracks) {
                this.tracks = tracks;
            }
            getAudioTracks() {
                return this.tracks;
            }
        },
    });
}

test("SessionRecorder uses the correct extension for Safari-compatible MP4 audio", async () => {
    patchWebAudio("audio/mp4");
    const sipSession = new EventTarget();
    sipSession.stateChange = { addListener: () => {} };

    const recorder = new SessionRecorder(sipSession, 123);

    expect.verifySteps([
        "connect:GainNode->MediaStreamAudioDestinationNode",
        "connect:GainNode->MediaStreamAudioDestinationNode",
    ]);
    expect(recorder.outputMimeType).toBe("audio/mp4");
    expect(recorder.outputFileExtension).toBe("m4a");
    await recorder._terminate();
    expect.verifySteps(["audio-context:close"]);
});

test("SessionRecorder dynamic track updates", async () => {
    patchWebAudio();
    const sipSession = new EventTarget();
    sipSession.stateChange = { addListener: () => {} };

    const recorder = new SessionRecorder(sipSession, 123);

    // Initial state: AudioContext is created, but no tracks connected yet
    expect(recorder._audioContext.state).toBe("running");
    expect.verifySteps([
        "connect:GainNode->MediaStreamAudioDestinationNode",
        "connect:GainNode->MediaStreamAudioDestinationNode",
    ]);

    // 1. Add Initial tracks
    const mic1 = makeTrack("mic1");
    const remote1 = makeTrack("remote1");

    recorder.updateLocalTrack(mic1);
    expect.verifySteps(["connect:MediaStreamSourceNode->GainNode", "wire:mic1->GainNode"]);

    recorder.updateRemoteTrack(remote1);
    expect.verifySteps(["connect:MediaStreamSourceNode->GainNode", "wire:remote1->GainNode"]);

    // 2. Mid-call device swap (Microphone)
    const mic2 = makeTrack("mic2");
    recorder.updateLocalTrack(mic2);
    expect.verifySteps([
        "disconnect:MediaStreamSourceNode",
        "connect:MediaStreamSourceNode->GainNode",
        "wire:mic2->GainNode",
    ]);

    // 3. Cleanup
    await recorder._terminate();
    expect.verifySteps(["audio-context:close"]);
});

test("SessionRecorder rotates recording chunks", async () => {
    patchWebAudio("audio/ogg;codecs=opus");
    patchWithCleanup(SessionRecorder, { CHUNK_DURATION_MS: 100 });
    patchWithCleanup(SessionRecorder.prototype, {
        _uploadChunk() {
            expect.step("chunk:upload");
            return Promise.resolve();
        },
    });

    const recorder = new SessionRecorder(null, 123, true);
    expect.verifySteps([
        "connect:GainNode->MediaStreamAudioDestinationNode",
        "connect:GainNode->MediaStreamAudioDestinationNode",
        "recorder:start",
    ]);

    await advanceTime(100);

    expect.verifySteps(["recorder:stop", "chunk:upload", "recorder:start"]);
    recorder.recordOff();
    expect.verifySteps(["recorder:stop", "chunk:upload"]);
    await recorder._terminate();
    expect.verifySteps(["audio-context:close"]);
});

test("SessionRecorder termination waits for active uploads", async () => {
    patchWebAudio();
    const { promise, resolve } = Promise.withResolvers();
    patchWithCleanup(SessionRecorder.prototype, {
        _performUpload() {
            expect.step("chunk:upload");
            return promise;
        },
    });

    const recorder = new SessionRecorder(null, 123);
    expect.verifySteps([
        "connect:GainNode->MediaStreamAudioDestinationNode",
        "connect:GainNode->MediaStreamAudioDestinationNode",
    ]);
    recorder._uploadChunk(new Blob(["audio"], { type: "audio/ogg" }), 0, 100);
    expect.verifySteps(["chunk:upload"]);

    let didTerminate = false;
    const termination = recorder._terminate().then(() => {
        didTerminate = true;
    });
    await Promise.resolve();

    expect(didTerminate).toBe(false);
    expect(SessionRecorder.uploadsByRecorder.has(recorder)).toBe(true);
    expect.verifySteps(["audio-context:close"]);

    resolve();
    await termination;

    expect(didTerminate).toBe(true);
    expect(SessionRecorder.uploadsByRecorder.has(recorder)).toBe(false);
});
