import { describe, expect, test } from "@odoo/hoot";
import { tick } from "@odoo/hoot-mock";
import { start } from "@mail/../tests/mail_test_helpers";
import { AudioManager } from "@voip/core/web/audio_manager";
import { Ringtone } from "@voip/core/web/ringtone";
import { setupVoipTests } from "@voip/../tests/voip_test_helpers";
import { getService, patchWithCleanup } from "@web/../tests/web_test_helpers";
import { proxy } from "@odoo/owl";

describe.current.tags("desktop");
setupVoipTests();

function patchAudio(options = {}) {
    class FakeAudio {
        static instances = [];

        constructor() {
            this.srcObject = null;
            this.sinkId = "";
            FakeAudio.instances.push(this);
        }

        play() {
            options.play?.();
            return Promise.resolve();
        }

        pause() {
            options.pause?.();
        }

        load() {
            options.load?.();
        }

        async setSinkId(deviceId) {
            this.sinkId = deviceId;
            options.setSinkId?.(deviceId);
        }
    }
    patchWithCleanup(window, { Audio: FakeAudio });
    return FakeAudio;
}

function patchAudioContextWithEmptyStream() {
    const emptyStream = {
        getTracks: () => [
            {
                stop() {
                    expect.step("empty-stream:stop");
                },
            },
        ],
    };
    class FakeAudioContext {
        constructor() {
            this.state = "running";
        }

        createMediaStreamDestination() {
            return { stream: emptyStream };
        }

        close() {
            this.state = "closed";
            expect.step("audio-context:close");
        }
    }
    patchWithCleanup(window, { AudioContext: FakeAudioContext });
    return emptyStream;
}

function patchMediaDevices(getUserMedia) {
    patchWithCleanup(navigator.mediaDevices, { getUserMedia });
}

async function makeVoip({ rtc = {}, settings = {}, triggerError, ...extra } = {}) {
    await start();
    const store = getService("mail.store");
    Object.assign(store.rtc, { microphonePermission: "granted", ...rtc });
    Object.assign(store.settings, {
        audioOutputDeviceId: "",
        ringtoneOutputDeviceId: "",
        ...settings,
    });
    const voip = {
        microphoneError: null,
        store,
        triggerError: triggerError || (() => () => {}),
    };
    return proxy({ ...voip, ...extra });
}

function makeLiveAudioStream(stepName) {
    const track = {
        kind: "audio",
        readyState: "live",
        enabled: true,
        clone() {
            return {
                kind: "audio",
                readyState: "live",
                enabled: true,
                isClone: true,
                stop() {
                    expect.step(`${stepName}:clone-stop`);
                },
            };
        },
        stop() {
            expect.step(`${stepName}:stop`);
        },
    };
    return {
        getAudioTracks: () => [track],
        getTracks: () => [track],
    };
}

function makeSessionDescriptionHandler(extra = {}) {
    return {
        close() {},
        remoteMediaStream: new EventTarget(),
        ...extra,
    };
}

test("setupSessionDescriptionHandler wires remote audio and cleans it up on close", async () => {
    const FakeAudio = patchAudio({
        play() {
            expect.step("audio:play");
        },
        pause() {
            expect.step("audio:pause");
        },
        load() {
            expect.step("audio:load");
        },
    });

    const manager = new AudioManager(await makeVoip());
    const remoteMediaStream = new EventTarget();
    const sessionDescriptionHandler = {
        remoteMediaStream,
        close() {
            expect.step("sdh:close");
        },
    };

    manager.setupSessionDescriptionHandler(sessionDescriptionHandler, "outgoing", () => {
        expect.step("remote-track");
    });

    remoteMediaStream.dispatchEvent(new Event("addtrack"));
    expect.verifySteps(["remote-track", "audio:play"]);

    const remoteAudio = FakeAudio.instances[0];
    expect(remoteAudio.srcObject).toBe(remoteMediaStream);

    sessionDescriptionHandler.close();
    expect.verifySteps(["sdh:close", "audio:pause", "audio:load"]);
    expect(remoteAudio.srcObject).toBe(null);
});

test("setupSessionDescriptionHandler applies preferred call output device", async () => {
    const FakeAudio = patchAudio({
        setSinkId(deviceId) {
            expect.step(`set-sink:${deviceId}`);
        },
    });

    const manager = new AudioManager(
        await makeVoip({
            settings: { audioOutputDeviceId: "speaker-1" },
        })
    );
    const sessionDescriptionHandler = makeSessionDescriptionHandler();
    manager.setupSessionDescriptionHandler(sessionDescriptionHandler, "outgoing", () => {});
    await manager._deviceUpdateMutex.getUnlockedDef();

    expect(FakeAudio.instances.length).toBe(1);
    expect(FakeAudio.instances[0].sinkId).toBe("speaker-1");
    expect.verifySteps(["set-sink:speaker-1"]);
});

test("registered ringtone follows ringtone output changes before a session handler exists", async () => {
    patchAudio({
        setSinkId(deviceId) {
            expect.step(`set-sink:${deviceId}`);
        },
    });

    const voip = await makeVoip({
        settings: { ringtoneOutputDeviceId: "speaker-1" },
    });
    const manager = new AudioManager(voip);
    const ringtone = new Ringtone();

    await manager.registerRingtone(ringtone);

    expect(ringtone.audio.sinkId).toBe("speaker-1");
    expect.verifySteps(["set-sink:speaker-1"]);

    voip.store.settings.ringtoneOutputDeviceId = "speaker-2";
    await manager.applyOutputDeviceToRingtones();

    expect(ringtone.audio.sinkId).toBe("speaker-2");
    expect.verifySteps(["set-sink:speaker-2"]);

    manager.unregisterRingtone(ringtone);
    voip.store.settings.ringtoneOutputDeviceId = "speaker-3";
    await manager.applyOutputDeviceToRingtones();

    expect(ringtone.audio.sinkId).toBe("speaker-2");
    expect.verifySteps([]);
});

test("requestMediaStreamForSIP cleans up previous stream when source is replaced", async () => {
    patchAudio();
    let callCount = 0;
    patchMediaDevices(async () => {
        callCount++;
        expect.step(`get-user-media:${callCount}`);
        return makeLiveAudioStream(`stream-${callCount}`);
    });

    const manager = new AudioManager(await makeVoip());
    const sessionDescriptionHandler = makeSessionDescriptionHandler();
    manager.setupSessionDescriptionHandler(sessionDescriptionHandler, "outgoing", () => {});

    await manager.requestMediaStreamForSIP({ audio: true }, sessionDescriptionHandler);
    await manager.requestMediaStreamForSIP({ audio: true }, sessionDescriptionHandler);

    expect.verifySteps(["get-user-media:1", "get-user-media:2", "stream-1:stop"]);

    sessionDescriptionHandler.close();
    expect.verifySteps(["stream-2:stop"]);
});

test("requestMediaStreamForSIP creates an empty stream when audio is not requested", async () => {
    patchAudio();
    patchMediaDevices(async () => {
        expect.step("get-user-media");
    });
    // The patch is to make sure getUserMedia is not called later in the test.
    // Make sure the patch works first.
    navigator.mediaDevices.getUserMedia();
    expect.verifySteps(["get-user-media"]);
    const emptyStream = patchAudioContextWithEmptyStream();

    const manager = new AudioManager(await makeVoip());
    const sessionDescriptionHandler = makeSessionDescriptionHandler();
    manager.setupSessionDescriptionHandler(sessionDescriptionHandler, "outgoing", () => {});

    const stream = await manager.requestMediaStreamForSIP(
        { audio: false },
        sessionDescriptionHandler
    );

    expect(stream).toBe(emptyStream);
    expect.verifySteps([]);

    sessionDescriptionHandler.close();
    expect.verifySteps(["empty-stream:stop", "audio-context:close"]);
});

test("requestMediaStreamForSIP falls back to empty stream on microphone error", async () => {
    patchAudio();
    const mediaError = new DOMException("No input device", "NotFoundError");
    patchMediaDevices(async () => {
        expect.step("get-user-media");
        return Promise.reject(mediaError);
    });
    const emptyStream = patchAudioContextWithEmptyStream();

    let triggerErrorCalls = 0;
    const voip = await makeVoip({
        triggerError() {
            triggerErrorCalls++;
            return () => {};
        },
    });
    const manager = new AudioManager(voip);
    const sessionDescriptionHandler = makeSessionDescriptionHandler();
    manager.setupSessionDescriptionHandler(sessionDescriptionHandler, "outgoing", () => {});

    const stream = await manager.requestMediaStreamForSIP(
        { audio: true },
        sessionDescriptionHandler
    );

    expect(stream).toBe(emptyStream);
    expect(triggerErrorCalls).toBe(0);
    expect(Boolean(voip.microphoneError)).toBe(true);
    expect.verifySteps(["get-user-media"]);

    sessionDescriptionHandler.close();
    expect.verifySteps(["empty-stream:stop", "audio-context:close"]);
});

test("requestMediaStreamForSIP shows permission dialog for outgoing prompt and uses empty stream when dismissed", async () => {
    patchAudio();
    const emptyStream = patchAudioContextWithEmptyStream();
    patchMediaDevices(async () => {
        expect.step("get-user-media");
        return makeLiveAudioStream("stream");
    });

    const voip = await makeVoip({
        rtc: {
            microphonePermission: "prompt",
            showMediaPermissionDialog(kind, configuration) {
                expect.step(`show-dialog:${kind}`);
                configuration.options.onClose({ dismiss: true });
            },
        },
        softphone: {
            audioPermissionDialogConfiguration: {
                options: {
                    onClose() {
                        expect.step("dialog:close");
                    },
                },
            },
        },
    });
    const manager = new AudioManager(voip);
    const sessionDescriptionHandler = makeSessionDescriptionHandler();
    manager.setupSessionDescriptionHandler(sessionDescriptionHandler, "outgoing", () => {});

    const stream = await manager.requestMediaStreamForSIP(
        { audio: true },
        sessionDescriptionHandler
    );

    expect(stream).toBe(emptyStream);
    expect.verifySteps(["show-dialog:microphone", "dialog:close"]);

    sessionDescriptionHandler.close();
    expect.verifySteps(["empty-stream:stop", "audio-context:close"]);
});

test("requestMediaStreamForSIP requests microphone after outgoing prompt dialog if not dismissed", async () => {
    patchAudio();
    const sourceStream = makeLiveAudioStream("stream");
    patchMediaDevices(async () => {
        expect.step("get-user-media");
        return sourceStream;
    });

    const voip = await makeVoip({
        rtc: {
            microphonePermission: "prompt",
            showMediaPermissionDialog(kind, configuration) {
                expect.step(`show-dialog:${kind}`);
                configuration.options.onClose({ dismiss: false });
            },
        },
        softphone: {
            audioPermissionDialogConfiguration: {
                options: {
                    onClose() {
                        expect.step("dialog:close");
                    },
                },
            },
        },
    });
    const manager = new AudioManager(voip);
    const sessionDescriptionHandler = makeSessionDescriptionHandler();
    manager.setupSessionDescriptionHandler(sessionDescriptionHandler, "outgoing", () => {});

    const stream = await manager.requestMediaStreamForSIP(
        { audio: true },
        sessionDescriptionHandler
    );

    expect(stream).toBe(sourceStream);
    expect.verifySteps(["show-dialog:microphone", "dialog:close", "get-user-media"]);

    sessionDescriptionHandler.close();
    expect.verifySteps(["stream:stop"]);
});

test("requestMediaStreamForSIP does not show permission dialog for incoming prompt calls", async () => {
    patchAudio();
    const sourceStream = makeLiveAudioStream("stream");
    patchMediaDevices(async () => {
        expect.step("get-user-media");
        return sourceStream;
    });

    const voip = await makeVoip({
        rtc: {
            microphonePermission: "prompt",
            showMediaPermissionDialog() {
                expect.step("show-dialog");
            },
        },
        softphone: {
            audioPermissionDialogConfiguration: {
                options: { onClose() {} },
            },
        },
    });
    const manager = new AudioManager(voip);
    const sessionDescriptionHandler = makeSessionDescriptionHandler();
    manager.setupSessionDescriptionHandler(sessionDescriptionHandler, "incoming", () => {});

    const stream = await manager.requestMediaStreamForSIP(
        { audio: true },
        sessionDescriptionHandler
    );

    expect(stream).toBe(sourceStream);
    expect.verifySteps(["get-user-media"]);

    sessionDescriptionHandler.close();
    expect.verifySteps(["stream:stop"]);
});

test("requestMediaStream uses selected input device constraint", async () => {
    patchAudio();
    let constraints;
    patchMediaDevices(async (c) => {
        constraints = c;
        return makeLiveAudioStream("stream");
    });

    const manager = new AudioManager(
        await makeVoip({
            settings: {
                audioInputDeviceId: "mic-2",
            },
        })
    );
    const stream = await manager.requestMediaStream(false);

    expect(stream.getAudioTracks().length).toBe(1);
    expect(Boolean(constraints)).toBe(true);
    expect(constraints.audio.deviceId.exact).toBe("mic-2");
    expect(constraints.audio.echoCancellation).toBe(true);
});

test("refreshMicrophoneStatus relies on rtc microphone permission state", async () => {
    patchWithCleanup(navigator.mediaDevices, {
        async enumerateDevices() {
            return [{ kind: "audioinput" }];
        },
    });

    const voip = await makeVoip({
        rtc: { microphonePermission: "prompt" },
    });
    const manager = new AudioManager(voip);
    const refreshMicrophoneStatus = manager._refreshMicrophoneStatus.bind(manager);
    manager._refreshMicrophoneStatus = () => {
        expect.step("refresh");
        return refreshMicrophoneStatus();
    };
    await manager.setup();

    expect(Boolean(voip.microphoneError)).toBe(true);
    expect.verifySteps(["refresh"]);

    voip.store.rtc.microphonePermission = "granted";
    await tick();
    expect(voip.microphoneError).toBe(null);
    expect.verifySteps(["refresh"]);
});

test("applyInputDeviceToSessions replaces sender tracks for active sessions", async () => {
    patchAudio();
    const sourceStream = makeLiveAudioStream("track");
    patchMediaDevices(async () => {
        expect.step("get-user-media");
        return sourceStream;
    });

    const sender = {
        track: { kind: "audio", enabled: false },
        async replaceTrack(track) {
            expect.step("replace-track");
            this.track = track;
        },
    };
    const sessionDescriptionHandler = makeSessionDescriptionHandler({
        peerConnection: {
            getSenders() {
                return [sender];
            },
        },
    });
    const manager = new AudioManager(await makeVoip());
    manager.setupSessionDescriptionHandler(sessionDescriptionHandler, "outgoing", () => {});

    await manager.applyInputDeviceToSessions(false);

    expect.verifySteps(["get-user-media", "replace-track"]);
    expect(sender.track.isClone).toBe(true);
    expect(sender.track.enabled).toBe(false); // As the sender original track was not enabled

    sessionDescriptionHandler.close();
    expect.verifySteps(["track:clone-stop", "track:stop"]);
});

test("input device choice updates live sessions and does nothing out of call", async () => {
    patchAudio();

    const manager = new AudioManager(await makeVoip());
    patchWithCleanup(manager, {
        _refreshMicrophoneStatus() {
            expect.step("refresh");
        },
        applyInputDeviceToSessions(forceErrorDisplay, forceStreamRequest) {
            expect.step(`apply-input:${forceErrorDisplay}:${forceStreamRequest}`);
        },
    });

    manager._onInputDeviceChoice();
    expect.verifySteps(["refresh"]);

    manager._sdhToData.set(makeSessionDescriptionHandler(), {
        remoteAudio: new Audio(),
    });
    manager._onInputDeviceChoice();
    expect.verifySteps(["refresh", "apply-input:false:true"]);
});

test("output device choice applies preferred output to active sessions", async () => {
    patchAudio({
        setSinkId(deviceId) {
            expect.step(`set-sink:${deviceId}`);
        },
    });

    const voip = await makeVoip({
        settings: { audioOutputDeviceId: "speaker-2" },
    });
    const manager = new AudioManager(voip);
    const sdh1 = makeSessionDescriptionHandler();
    const sdh2 = makeSessionDescriptionHandler();
    const audio1 = new Audio();
    const audio2 = new Audio();
    manager._sdhToData.set(sdh1, { remoteAudio: audio1 });
    manager._sdhToData.set(sdh2, { remoteAudio: audio2 });

    await manager.applyOutputDeviceToSessions();
    await manager._deviceUpdateMutex.getUnlockedDef();
    expect(audio1.sinkId).toBe("speaker-2");
    expect(audio2.sinkId).toBe("speaker-2");
    // Only the 2 call audio elements are updated. Ringtones now use their own
    // output device setting.
    expect.verifySteps(["set-sink:speaker-2", "set-sink:speaker-2"]);

    voip.store.settings.audioOutputDeviceId = "speaker-1";
    manager._onOutputDeviceChoice();
    await manager._deviceUpdateMutex.getUnlockedDef();
    expect(audio1.sinkId).toBe("speaker-1");
    expect(audio2.sinkId).toBe("speaker-1");
    expect.verifySteps(["set-sink:speaker-1", "set-sink:speaker-1"]);

    manager._sdhToData.clear();
    manager._onOutputDeviceChoice();
    await manager._deviceUpdateMutex.getUnlockedDef();
    expect.verifySteps([]);
});

test("ringtone output device choice applies to all session ringtones", async () => {
    patchAudio({
        setSinkId(deviceId) {
            expect.step(`set-sink:${deviceId}`);
        },
    });

    const voip = await makeVoip({
        settings: { ringtoneOutputDeviceId: "speaker-2" },
    });
    const manager = new AudioManager(voip);
    const sdh1 = makeSessionDescriptionHandler();
    const audio1 = new Audio();
    const ringtone1 = new Ringtone();
    const ringtone2 = new Ringtone();
    manager._sdhToData.set(sdh1, { remoteAudio: audio1 });
    manager.registerRingtone(ringtone1);
    // Incoming sessions can start ringing before they have a session
    // description handler. Their ringtone must be updated too.
    manager.registerRingtone(ringtone2);

    await manager._deviceUpdateMutex.getUnlockedDef();
    expect(ringtone1.audio.sinkId).toBe("speaker-2");
    expect(ringtone2.audio.sinkId).toBe("speaker-2");
    expect(audio1.sinkId).toBe("");
    expect.verifySteps(["set-sink:speaker-2", "set-sink:speaker-2"]);

    voip.store.settings.ringtoneOutputDeviceId = "speaker-1";
    manager._onRingtoneOutputDeviceChoice();
    await manager._deviceUpdateMutex.getUnlockedDef();
    expect(ringtone1.audio.sinkId).toBe("speaker-1");
    expect(ringtone2.audio.sinkId).toBe("speaker-1");
    expect(audio1.sinkId).toBe("");
    expect.verifySteps(["set-sink:speaker-1", "set-sink:speaker-1"]);

    manager.unregisterRingtone(ringtone1);
    manager.unregisterRingtone(ringtone2);
    manager._onRingtoneOutputDeviceChoice();
    await manager._deviceUpdateMutex.getUnlockedDef();
    expect.verifySteps([]);
});

test("applyOutputDeviceToSession clears preferred device when setSinkId fails", async () => {
    let setSinkIdCalls = 0;
    patchAudio({
        setSinkId(deviceId) {
            setSinkIdCalls++;
            expect.step(`set-sink:${deviceId}:${setSinkIdCalls}`);
            if (setSinkIdCalls === 1) {
                throw new DOMException("Failed to switch sink", "AbortError");
            }
        },
    });

    const voip = await makeVoip({
        settings: { audioOutputDeviceId: "speaker-bad" },
    });
    const manager = new AudioManager(voip);
    await manager.setup();
    const sessionDescriptionHandler = makeSessionDescriptionHandler();
    manager.setupSessionDescriptionHandler(sessionDescriptionHandler, "outgoing", () => {});

    await manager._deviceUpdateMutex.getUnlockedDef();
    // Only call audio is configured here; ringtones are registered separately.
    expect.verifySteps(["set-sink:speaker-bad:1", "set-sink::2"]);
    expect(voip.store.settings.audioOutputDeviceId).toBe("");
});

test("applyOutputDeviceToRingtone clears only the preferred ringtone device on failure", async () => {
    patchAudio({
        setSinkId(deviceId) {
            expect.step(`set-sink:${deviceId}`);
            if (deviceId === "speaker-bad") {
                throw new DOMException("Failed to switch sink", "AbortError");
            }
        },
    });

    const voip = await makeVoip({
        settings: {
            audioOutputDeviceId: "speaker-good",
            ringtoneOutputDeviceId: "speaker-bad",
        },
    });
    const manager = new AudioManager(voip);
    await manager.setup();
    manager.registerRingtone(new Ringtone());

    await manager._deviceUpdateMutex.getUnlockedDef();
    expect.verifySteps(["set-sink:speaker-bad", "set-sink:"]);
    expect(voip.store.settings.audioOutputDeviceId).toBe("speaker-good");
    expect(voip.store.settings.ringtoneOutputDeviceId).toBe("");
});

test("applyInputDeviceToSessions with force display cleans active sources and shows error", async () => {
    patchAudio();
    let callCount = 0;
    patchMediaDevices(async () => {
        callCount++;
        expect.step(`get-user-media:${callCount}`);
        if (callCount === 1) {
            return makeLiveAudioStream("stream-1");
        }
        const mediaError = new DOMException("Permission denied", "NotAllowedError");
        return Promise.reject(mediaError);
    });

    let triggerErrorPayload;
    const voip = await makeVoip({
        triggerError(payload) {
            triggerErrorPayload = payload;
            expect.step("trigger-error");
            return () => {};
        },
    });
    const manager = new AudioManager(voip);
    const sessionDescriptionHandler = makeSessionDescriptionHandler();
    manager.setupSessionDescriptionHandler(sessionDescriptionHandler, "outgoing", () => {});

    await manager.requestMediaStreamForSIP({ audio: true }, sessionDescriptionHandler);
    await manager.applyInputDeviceToSessions(true, true);

    expect(Boolean(voip.microphoneError)).toBe(true);
    expect(triggerErrorPayload.technical).toBe("NotAllowedError");
    expect(triggerErrorPayload.technicalExtra).toBe("Permission denied");

    expect.verifySteps(["get-user-media:1", "get-user-media:2", "stream-1:stop", "trigger-error"]);

    sessionDescriptionHandler.close();
    expect.verifySteps([]);
});
