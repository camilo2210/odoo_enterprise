import { describe, expect, test } from "@odoo/hoot";
import { patch } from "@web/core/utils/patch";
import { AudioManager } from "@voip/core/web/audio_manager";
import { Session } from "@voip/core/web/session";

describe.current.tags("headless");

const SIP = {
    SessionState: {
        Initial: "Initial",
        Establishing: "Establishing",
        Established: "Established",
        Terminated: "Terminated",
    },
};

test("updates an incoming call based on its SIP cancellation reason", async () => {
    const cases = [
        {
            label: "completed elsewhere",
            reason: 'SIP;cause=200;text="Call completed elsewhere"',
            status: "completed_elsewhere",
            action: "completeElsewhere",
        },
        {
            label: "Q.850 completed elsewhere",
            reason: "Q.850;cause=26",
            status: "completed_elsewhere",
            action: "completeElsewhere",
        },
        { label: "SIP rejection", reason: "SIP;cause=603", status: "rejected", action: "reject" },
        {
            label: "Q.850 rejection",
            reason: "Q.850;cause=21",
            status: "rejected",
            action: "reject",
        },
        { label: "missed", reason: "SIP;cause=487", status: "missed", action: "miss" },
    ];

    for (const { label, reason, status, action } of cases) {
        const call = Object.fromEntries(
            ["completeElsewhere", "reject", "miss"].map((method) => [
                method,
                async () => {
                    expect.step(`${label}: ${method}`);
                },
            ])
        );
        const { session, sipSession } = makeSession({ callProm: Promise.resolve(call) });

        sipSession.delegate.onCancel({
            request: { getHeader: () => reason },
        });
        await session.callProm;

        expect(session.status).toBe(status);
        expect.verifySteps([`${label}: ${action}`]);
    }
});

test("plays remote audio when a remote audio track is added before state changes", async () => {
    let playCount = 0;

    class FakeAudio {
        constructor() {
            this.srcObject = null;
        }
        play() {
            playCount += 1;
            return Promise.resolve();
        }
        pause() {}
        load() {}
        removeAttribute() {}
        async setSinkId() {}
    }

    patch(window, {
        Audio: FakeAudio,
    });

    class FakeRemoteMediaStream extends EventTarget {
        addTrack(track) {
            const event = new Event("addtrack");
            Object.defineProperty(event, "track", { value: track });
            this.dispatchEvent(event);
        }
    }

    const voip = {
        bus: { trigger() {} },
        store: {
            rtc: {},
            settings: {
                audioOutputDeviceId: "",
            },
        },
        triggerError: () => () => {},
    };
    const audioManager = new AudioManager(voip);
    const remoteMediaStream = new FakeRemoteMediaStream();
    const sessionDescriptionHandler = { close() {}, remoteMediaStream };
    const sipSession = {
        stateChange: { addListener() {} },
        sessionDescriptionHandler,
        delegate: {},
    };
    new Session(voip, {
        direction: "incoming",
        callProm: new Promise(() => {}),
        sipSession,
        onSessionDescriptionHandler: audioManager.setupSessionDescriptionHandler.bind(audioManager),
    });
    sipSession.delegate.onSessionDescriptionHandler(sessionDescriptionHandler);

    remoteMediaStream.addTrack({ kind: "audio" });
    expect(playCount).toBe(1);
    await audioManager._deviceUpdateMutex.getUnlockedDef();
});

function makeSession({ callProm = Promise.resolve({ start() {}, end() {}, id: 1 }) } = {}) {
    patch(window, { SIP });
    let stateListener;
    const sipSession = {
        state: SIP.SessionState.Initial,
        stateChange: {
            addListener(listener) {
                stateListener = listener;
            },
        },
        delegate: {},
        sessionDescriptionHandler: {
            enableReceiverTracks() {},
            enableSenderTracks() {},
        },
    };
    const voip = {
        bus: { trigger() {} },
        config: { recordingPolicy: "disabled" },
        resolveError() {},
        triggerError: () => () => {},
    };
    const session = new Session(voip, {
        callProm,
        createDate: luxon.DateTime.now(),
        direction: "incoming",
        phone_number: "123",
        sipSession,
    });
    return {
        session,
        setState(state) {
            sipSession.state = state;
            stateListener(state);
        },
        sipSession,
    };
}

test("a hold requested before establishment is signaled once established", async () => {
    const { session, setState, sipSession } = makeSession();
    session.isOnHold = true;
    expect(session.isOnHold).toBe(true);
    sipSession.invite = async (options) => {
        expect(options.sessionDescriptionHandlerOptions.hold).toBe(true);
        expect.step("hold requested");
        options.requestDelegate.onAccept();
    };

    setState(SIP.SessionState.Established);
    await Promise.resolve();

    expect.verifySteps(["hold requested"]);
    setState(SIP.SessionState.Terminated);
});

test("the latest hold state wins when SIP responses arrive asynchronously", async () => {
    const { session, setState, sipSession } = makeSession();
    const requests = [];
    sipSession.invite = (options) => {
        const deferred = Promise.withResolvers();
        requests.push({ deferred, options });
        return deferred.promise;
    };
    setState(SIP.SessionState.Established);

    session.isOnHold = true;
    session.isOnHold = false;
    await Promise.resolve();
    expect(requests).toHaveLength(1);
    expect(requests[0].options.sessionDescriptionHandlerOptions.hold).toBe(true);

    requests[0].options.requestDelegate.onAccept();
    requests[0].deferred.resolve();
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
    expect(requests).toHaveLength(2);
    expect(requests[1].options.sessionDescriptionHandlerOptions.hold).toBe(false);

    requests[1].options.requestDelegate.onAccept();
    requests[1].deferred.resolve();
    await Promise.resolve();
    expect(session.isOnHold).toBe(false);
    setState(SIP.SessionState.Terminated);
});

test("termination cleans timer, ringtone and recorder", () => {
    const { session, setState } = makeSession();
    session.ringtone = { play() {}, stop: () => expect.step("ringtone stopped") };
    session.recorder = { recordOff: () => expect.step("recorder stopped") };

    setState(SIP.SessionState.Established);
    expect(Boolean(session.timer.interval)).toBe(true);
    expect.verifySteps(["ringtone stopped"]);

    setState(SIP.SessionState.Terminated);

    expect(session.timer.interval).toBe(undefined);
    expect.verifySteps(["ringtone stopped", "recorder stopped"]);
});

test("termination while waiting for the call record prevents late recorder setup", async () => {
    const { promise, resolve } = Promise.withResolvers();
    const { session, setState } = makeSession({ callProm: promise });
    session.voip.config.recordingPolicy = "always";

    setState(SIP.SessionState.Established);
    setState(SIP.SessionState.Terminated);
    resolve({ id: 1, start() {}, end() {} });
    await promise;
    await Promise.resolve();

    expect(session.recorder).toBe(null);
});

test("marks an incoming call as missed when the unanswered invitation expires", async () => {
    const call = {
        miss() {
            expect.step("miss");
        },
    };
    const { session, setState } = makeSession({ callProm: Promise.resolve(call) });

    setState(SIP.SessionState.Terminated);
    await session.callProm;

    expect(session.status).toBe("missed");
    expect.verifySteps(["miss"]);
});

// Tests _isRejecting
test("keeps a locally rejected incoming call rejected when its session terminates", async () => {
    const call = {
        reject() {
            expect.step("reject");
        },
    };
    const { session, setState, sipSession } = makeSession({ callProm: Promise.resolve(call) });
    sipSession.reject = () => {
        expect.step("SIP reject");
        setState(SIP.SessionState.Terminated);
        return Promise.resolve();
    };

    await session.reject();

    expect(session.status).toBe("rejected");
    expect.verifySteps(["SIP reject", "reject"]);
});
