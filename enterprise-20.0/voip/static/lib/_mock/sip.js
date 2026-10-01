/** @odoo-module */
/** partial copy of SIP.EmitterImpl */
class EmitterImpl {
    constructor() {
        this.listeners = new Array();
    }
    addListener(listener) {
        this.listeners.push(listener);
    }
    emit(data) {
        this.listeners.slice().forEach((listener) => listener(data));
    }
}

export const SessionState = {
    Initial: "Initial",
    Establishing: "Establishing",
    Established: "Established",
    Terminating: "Terminating",
    Terminated: "Terminated",
};

/**
 * We want the demo mode to look very similar to the production mode. So we create
 * a fake SIP session that mimics the behavior of a real SIP.js session.
 * This way, the rest of the code can mostly remain unchanged.
 *
 * @type {import("sip.js").Session}
 */
export class MockSipSession {
    isMock = true;
    /** @type {number} */
    static INVITE_DELAY = 3000;
    /** @type {{callId: string, localTag: string, remoteTag: string}|undefined} */
    dialog;

    state = SessionState.Initial;
    stateChange = new EmitterImpl();
    sessionDescriptionHandler = {
        peerConnection: {
            getReceivers: () => [],
            getSenders: () => {
                if (!this._localStream) {
                    return [];
                }
                return this._localStream.getTracks().map((track) => ({ track }));
            },
        },
        enableReceiverTracks(enable) {
            for (const receiver of this.peerConnection.getReceivers()) {
                if (receiver.track) {
                    receiver.track.enabled = enable;
                }
            }
        },
        enableSenderTracks(enable) {
            for (const sender of this.peerConnection.getSenders()) {
                if (sender.track) {
                    sender.track.enabled = enable;
                }
            }
        },
        remoteMediaStream: new MediaStream(),
    };
    _localStream = null;

    _changeState(newState) {
        this.state = newState;
        this.stateChange.emit(newState);
    }

    /**
     * The INVITE this session sends. Real sip.js builds it in the Inviter
     * constructor, so its Call-ID is readable before invite() — which is what
     * lets an outgoing call record correlate with the PBX webhooks describing
     * its leg.
     */
    get request() {
        return {
            getHeader: (name) => (name === "Call-ID" ? this._callId : null),
        };
    }

    get _callId() {
        if (!this.__callId) {
            this.__callId = `mock-call-id-${Math.random().toString(36).slice(2)}`;
        }
        return this.__callId;
    }

    _createDialog() {
        this.dialog = {
            callId: `mock-${Math.random().toString(36).slice(2)}`,
            localTag: `local-${Math.random().toString(36).slice(2)}`,
            remoteTag: `remote-${Math.random().toString(36).slice(2)}`,
        };
    }

    bye() {
        this._stopMockedMicStream();
        this._changeState(SessionState.Terminated);
        return Promise.resolve();
    }

    cancel() {
        clearTimeout(this.timeout);
        this._stopMockedMicStream();
        this._changeState(SessionState.Terminated);
        return Promise.resolve();
    }

    async invite(options = {}) {
        if (options.sessionDescriptionHandlerOptions?.hold !== undefined) {
            // Hold/unhold re-INVITE: call onAccept immediately (no SIP round-trip in demo)
            options.requestDelegate?.onAccept();
            return Promise.resolve();
        }
        await this._acquireMicMedia();
        this._changeState(SessionState.Establishing);
        this.timeout = setTimeout(() => {
            this._createDialog();
            this._changeState(SessionState.Established);
        }, this.constructor.INVITE_DELAY);
    }

    /** @returns {Promise<void>} */
    async accept() {
        await this._acquireMicMedia();
        this._createDialog();
        this._changeState(SessionState.Established);
    }

    /**
     * Acquires the local media stream (microphone) for the demo call.
     * @private
     * @returns {Promise<void>}
     */
    async _acquireMicMedia() {
        try {
            this._localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        } catch {
            // Silently ignore hardware failures or permission denials.
            // SessionRecorder and the UI are built to handle a null localStream gracefully.
        }
    }

    /**
     * Stops all tracks of the local media stream.
     * @private
     */
    _stopMockedMicStream() {
        if (this._localStream) {
            this._localStream.getTracks().forEach((track) => track.stop());
            this._localStream = null;
        }
    }

    refer(target, options = {}) {
        if (this.state !== SessionState.Established) {
            return Promise.reject(new Error(`Invalid session state ${this.state}`));
        }
        target.bye?.(); // for attended transfer: hangup target session
        if (options.requestDelegate && options.requestDelegate.onAccept) {
            options.requestDelegate.onAccept();
        }
        if (options.onNotify) {
            const incomingNotifyRequest = {
                message: {
                    body: "200 OK",
                },
            };
            options.onNotify({ incomingNotifyRequest });
        }
        return Promise.resolve();
    }
}

const RegistererState = {
    Initial: "Initial",
    Registered: "Registered",
    Unregistered: "Unregistered",
    Terminated: "Terminated",
};

class Registerer {
    static defaultExpires = 600;
    constructor(userAgent, options = {}) {
        this.userAgent = userAgent;
        this.expires = options.expires || Registerer.defaultExpires;
    }
    state = RegistererState.Initial;
    stateChange = new EmitterImpl();

    register() {
        this._changeState(RegistererState.Registered);
        return Promise.resolve();
    }

    unregister() {
        this._changeState(RegistererState.Unregistered);
        return Promise.resolve();
    }

    _changeState(newState) {
        this.state = newState;
        this.stateChange.emit(newState);
    }
}

export class UserAgent {
    static makeURI(uriString) {
        return {};
    }

    constructor(options = {}) {
        this.options = options;
    }

    start() {
        return Promise.resolve();
    }

    reconnect() {
        return Promise.resolve();
    }
}

class SessionDescriptionHandler {
    constructor(logger, mediaStreamFactory, sessionDescriptionHandlerConfiguration) {
        this.logger = logger;
        this.mediaStreamFactory = mediaStreamFactory;
        this.sessionDescriptionHandlerConfiguration = sessionDescriptionHandlerConfiguration;
    }
}

const Web = {
    defaultSessionDescriptionHandlerFactory(mediaStreamFactory) {
        return (session, options) => {
            const logger = null;
            const sessionDescriptionHandlerConfiguration = {};
            return new SessionDescriptionHandler(
                logger,
                mediaStreamFactory,
                sessionDescriptionHandlerConfiguration
            );
        };
    },
};

const SIPExtension = {
    Required: "Required",
    Supported: "Supported",
    Unsupported: "Unsupported",
};

export const SIP = {
    Inviter: MockSipSession,
    Registerer,
    RegistererState,
    Session: MockSipSession,
    SessionState,
    SIPExtension,
    UserAgent,
    version: "mocked-version",
    Web,
};

window.SIP = SIP;
