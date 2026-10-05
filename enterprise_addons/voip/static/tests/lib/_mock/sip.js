import { MockSipSession, SessionState, SIP, UserAgent } from "@voip/../lib/_mock/sip";

// Eliminate artificial delays in tests.
MockSipSession.INVITE_DELAY = 32; // 2 animation frame

class TestInvitation extends MockSipSession {
    static nextCallId = 1;
    static nextControlHandle = 1;
    constructor(userAgent, incomingInviteRequest) {
        super(userAgent);
        this.incomingInviteRequest = incomingInviteRequest || {
            message: {
                body: "",
                from: {
                    uri: {
                        user: "123456789",
                    },
                },
                getHeader: (name) =>
                    this._headers[name] ?? (name === "Call-ID" ? this._callId : null),
            },
        };
    }

    _headers = {};

    _configureWith(data = {}) {
        if (data.phone_number) {
            this.remoteIdentity.uri.user = data.phone_number;
        }
        if (data.sip_call_id) {
            this.__callId = data.sip_call_id;
        }
        if (data.headers) {
            Object.assign(this._headers, data.headers);
        }
    }

    get _callId() {
        if (!this.__callId) {
            this.__callId = `call-id-${TestInvitation.nextCallId++}`;
        }
        return this.__callId;
    }

    get body() {
        return this.incomingInviteRequest.message.body;
    }
    /**
     * The identity of the remote user.
     */
    get remoteIdentity() {
        return this.request.from;
    }
    /**
     * Initial incoming INVITE request message.
     */
    get request() {
        return this.incomingInviteRequest.message;
    }

    _onAccept() {}
    async accept(options = {}) {
        await super.accept(...arguments);
        this._onAccept(options);
    }

    _onProgress() {}
    progress(options = {}) {
        this._changeState(SessionState.Establishing);
        this._onProgress(options);
        return Promise.resolve();
    }

    _onReject() {}
    reject(options = {}) {
        this._changeState(SessionState.Terminated);
        this._onReject(options);
        return Promise.resolve();
    }

    refer(target, options = {}) {
        const result = super.refer(target, options);
        if (target?.raw) {
            const phoneNumber = this.remoteIdentity.uri.user;
            const sip_call_id = `from-refer-${TestInvitation.nextCallId++}`;
            setTimeout(() => {
                for (const agent of TestUserAgent._instances) {
                    const onInvite = agent.options?.delegate?.onInvite;
                    if (onInvite) {
                        const invitation = new TestInvitation();
                        invitation._configureWith({ sip_call_id, phone_number: phoneNumber });
                        onInvite(invitation);
                    }
                }
            });
        }
        return result;
    }
}

class TestUserAgent extends UserAgent {
    /** @type {Set<TestUserAgent>} Registry of all live TestUserAgent instances. */
    static _instances = new Set();

    static makeURI(uri) {
        const [, scheme, user, host, port] = uri.match(/([^:]+):([^@]+)@([^:]+):?(\d+)?/);
        const raw = { host, port, scheme, user };
        return { raw };
    }

    constructor(options = {}) {
        super(options);
        TestUserAgent._instances.add(this);
    }
}

window.SIP = {
    ...SIP,
    Invitation: TestInvitation,
    UserAgent: TestUserAgent,
};
