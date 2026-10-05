import { toRaw, proxy } from "@odoo/owl";
import { Ringtone } from "@voip/core/web/ringtone";
import { SessionRecorder } from "@voip/core/web/session_recorder";
import { formatTimerText } from "@voip/core/web/utils";
import { _t } from "@web/core/l10n/translation";

export class Session {
    static nextId = 1;

    /** @type {string} */
    key = String(Session.nextId++);
    /** @type {import("models").Call} */
    call = null;
    callProm = null;
    /** @type {?SessionRecorder} */
    recorder = null;
    /**
     * Whether the session is responsible for playing the incoming ringtone.
     *
     * @type {boolean}
     */
    ringleader = false;
    /** @type {Ringtone} */
    ringtone = new Ringtone();
    /** @type {string} */
    transferTarget;
    /** @type {?{ countryName: string, flagUrl: string, formatted: string, number: string }} */
    outboundNumber = null;
    /** @type {boolean} */
    _isMuted = false;
    /** @type {boolean} */
    _isOnHold = false;
    /** @type {boolean} */
    _requestedHoldState = false;
    /** @type {Promise<void>} */
    _holdRequest = Promise.resolve();
    /** @type {boolean} */
    _isRejecting = false;
    /** @type {boolean} */
    cancelRequested = false;
    /** @type {boolean} */
    _wasEstablished = false;
    /**
     * @type {boolean} When true, skips the server-side call state update (e.g.
     * hangup initial call during device transfer).
     */
    skipServerUpdate = false;
    /**
     * The equivalent object from the SIP.js library.
     *
     * @type {?import("sip.js").Session}
     */
    __sipJsSession = null;

    /**
     * @param {Object} voip
     * @param {Object} param
     * @param {luxon.DateTime} param.createDate
     * @param {"incoming"|"outgoing"} param.direction
     * @param {string} param.phone_number
     * @param {string} [param.alias]
     * @param {import("models").Call} param.callProm
     * @param {import("sip.js").Session} param.sipSession
     * @param {?{ countryName: string, flagUrl: string, formatted: string, number: string }} [param.outboundNumber=null]
     * @param {string|null} [param.transferTarget=null]
     * @param {Function} [param.onSessionDescriptionHandler=()=>{}]
     * @param {Function} [param.onIncomingRingtoneRequested=()=>{}]
     * @param {Function} [param.onSessionStateEstablished=()=>{}]
     * @param {Function} [param.onSessionStateTerminated=()=>{}]
     */
    constructor(
        voip,
        {
            createDate,
            direction,
            phone_number,
            alias,
            callProm,
            sipSession,
            outboundNumber = null,
            transferTarget = "",
            onSessionDescriptionHandler = () => {},
            onIncomingRingtoneRequested = () => {},
            onSessionStateEstablished = () => {},
            onSessionStateTerminated = () => {},
        }
    ) {
        this.voip = voip;
        this.createDate = createDate;
        this.direction = direction;
        this.phone_number = phone_number;
        this.alias = alias;
        this.callProm = callProm.then((call) => {
            this.call = call;
            if (call?.phone_number && this.phone_number !== call.phone_number) {
                // Wazo internal INVITEs identify the caller with the SIP
                // username (odoo-user-uuid), while the webhook-created
                // voip.call stores the readable extension or external number.
                // Once both sides are correlated, use the call value everywhere
                // the softphone displays the current session.
                this.phone_number = call.phone_number;
            }
            // If the timer started before the call data was loaded (race
            // between SIP session establishment and the RPC), recalibrate it
            // now that start_date is available. This ensures transferred calls
            // show the correct elapsed time from the original start_date.
            if (this.timer && call?.start_date) {
                this._stopTimer();
                this._startTimer();
            }
            this.voip.bus.trigger("session_changed");
        });
        this.__sipJsSession = sipSession;
        this.outboundNumber = outboundNumber;
        this.transferTarget = transferTarget;
        this.onSessionDescriptionHandler = onSessionDescriptionHandler;
        this.onIncomingRingtoneRequested = onIncomingRingtoneRequested;
        this.onSessionStateEstablished = onSessionStateEstablished;
        this.onSessionStateTerminated = onSessionStateTerminated;

        this.__sipJsSession.delegate = {
            onCancel: (response) => this._onCancel(response),
            onSessionDescriptionHandler: this._onSessionDescriptionHandler.bind(this),
        };
        this.__sipJsSession.stateChange.addListener((state) => this._onStateChanged(state));
    }

    /**
     * The caller's number in INTERNATIONAL display format when available
     * (computed server-side via phone_validation on voip.call), falling back
     * to the raw session number when there is no call record or no formatted
     * value.
     * @returns {string}
     */
    get phoneNumberFormatted() {
        return this.call?.phone_number_formatted || this.phone_number;
    }

    /**
     * The remote party's number, following the live call record: a transfer
     * rebinds the call to a new interlocutor while the session keeps the
     * original INVITE identity.
     * @returns {string}
     */
    get displayedPhoneNumber() {
        return this.call?.phone_number || this.phone_number;
    }

    /** @returns {import("sip.js").Core.Dialog|undefined} */
    get dialog() {
        return this.__sipJsSession?.dialog;
    }

    /** @returns {import("sip.js").Core.OutgoingRequestDelegate} */
    get inviteRequestDelegate() {
        return {
            onAccept: (response) => this._onOutgoingInviteAccepted(response),
            onProgress: (response) => this._onOutgoingInviteProgress(response),
            onReject: (response) => this._onOutgoingInviteRejected(response),
        };
    }

    get sipCallId() {
        // Wazo exposes the SIP Call-ID in its webhook as `sip_call_id`. Using
        // the same SIP header here lets notification clicks target the exact
        // INVITE received by this browser, even when the PBX forked one queue
        // conversation into multiple SIP legs.
        return this.__sipJsSession.request.getHeader("Call-ID");
    }

    get controlHandle() {
        // The conversation key shared by every leg: the Odoo provider's
        // X-Odoo-Conversation-Id when trusted, else the SIP Call-ID. Lets a
        // notification action match this session against the same key the
        // server derives from the call it notifies about.
        const sipCallId = this.__sipJsSession.request.getHeader("Call-ID");
        const conversationId = this.voip.config.usesOdooProvider
            ? this.__sipJsSession.request.getHeader("X-Odoo-Conversation-Id")
            : null;
        return conversationId || sipCallId;
    }

    /** @returns {boolean} */
    get canBeRecorded() {
        return this.isOngoing && this.call;
    }

    /** @returns {boolean} */
    get isCalling() {
        return [SIP.SessionState.Initial, SIP.SessionState.Establishing].includes(
            this.__sipJsSession.state
        );
    }

    /** @returns {boolean} */
    get isOngoing() {
        return [SIP.SessionState.Established, SIP.SessionState.Terminating].includes(
            this.__sipJsSession.state
        );
    }

    /** @returns {boolean} */
    get isInProgress() {
        return this.isCalling || this.isOngoing;
    }

    /** @returns {boolean} */
    get ringsBack() {
        return this.isCalling && this._outgoingInviteIsRinging;
    }

    /** @returns {string} */
    get timerText() {
        if (this.isCalling) {
            return _t("Calling...");
        }
        return formatTimerText(this.timer?.time ?? 0);
    }

    /** @returns {boolean} */
    get isOnHold() {
        return this._isOnHold;
    }

    /** @param {boolean} state */
    set isOnHold(state) {
        if (state === this._requestedHoldState) {
            return;
        }
        this._requestedHoldState = state;
        if (!this.isOngoing) {
            this._isOnHold = state;
            return;
        }
        this._holdRequest = this._holdRequest.then(() => this._requestHold(state));
    }

    /** @returns {boolean} */
    get isMuted() {
        return this._isMuted;
    }

    /** @param {boolean} state */
    set isMuted(state) {
        this._isMuted = state;
        this._applyCallStateToTracks();
    }

    get isRecording() {
        return Boolean(this.recorder?.isRecording);
    }

    get canToggleRecording() {
        return this.voip.config.recordingPolicy === "user" && this.canBeRecorded;
    }

    /** @returns {ReturnType<_t>|""} */
    get statusText() {
        if (this.isOnHold) {
            return _t("On hold");
        }
        return _t("Calling…");
    }

    /**
     * Toggles on the audio recording of the session.
     */
    toggleRecording() {
        if (!this.canToggleRecording) {
            return;
        }
        if (this.isRecording) {
            this.recorder?.recordOff();
        } else {
            this.recorder?.recordOn();
        }
    }

    _applyCallStateToTracks() {
        const sessionDescriptionHandler = this.__sipJsSession.sessionDescriptionHandler;
        if (!sessionDescriptionHandler?.peerConnection) {
            return;
        }
        sessionDescriptionHandler.enableReceiverTracks(!this.isOnHold);
        sessionDescriptionHandler.enableSenderTracks(!this.isOnHold && !this.isMuted);
    }

    /**
     * Triggered when a track is added to the remote media stream.
     *
     * @param {MediaStreamTrackEvent} ev
     */
    _onRemoteTrackAdded(ev) {
        if (ev.track.kind !== "audio") {
            return;
        }
        this.recorder?.updateRemoteTrack(ev.track);
        this.ringtone.stop();
        this._applyCallStateToTracks();
    }

    /**
     * Triggered when the local media track is updated (e.g. device swap).
     *
     * @param {MediaStreamTrack} track
     */
    _onLocalTrackUpdated(track) {
        this.recorder?.updateLocalTrack(track);
    }

    /**
     * Triggered when receiving a 2xx final response to the INVITE request.
     *
     * @param {import("sip.js").Core.IncomingResponse} response
     */
    _onOutgoingInviteAccepted(response) {
        this.ringtone.stop();
        if (this.transferTarget) {
            this.refer(this.transferTarget, {
                requestDelegate: {
                    onAccept: (response) => this.hangup(),
                },
            });
            return;
        }
    }

    /**
     * Triggered when receiving a 1xx provisional response to the INVITE request
     * (excepted code 100 responses).
     *
     * NOTE: Relying on provisional responses to implement behaviors seems like
     * a bad idea, as they may or may not be sent depending on the SIP server
     * implementation.
     *
     * @param {import("sip.js").Core.IncomingResponse} response
     */
    _onOutgoingInviteProgress(response) {
        const { statusCode } = response.message;
        if (statusCode !== 183 /* Session Progress */ && statusCode !== 180 /* Ringing */) {
            return;
        }
        this._outgoingInviteIsRinging = true;
        const remoteStream = this.__sipJsSession.sessionDescriptionHandler?.remoteMediaStream;
        const hasEarlyMedia = remoteStream?.getTracks().length > 0;
        if (!hasEarlyMedia) {
            this.ringtone.play("ringback");
        }
    }

    /**
     * Triggered when receiving a 4xx, 5xx, or 6xx final response to the
     * INVITE request.
     *
     * @param {import("sip.js").Core.IncomingResponse} response
     */
    _onOutgoingInviteRejected(response) {
        if (response.message.statusCode === 487 /* Request Terminated */) {
            // invitation has been canceled by the user, the session has
            // already been terminated
            return;
        }
        let message = "";
        let technicalExtra = "";
        switch (response.message.statusCode) {
            case 404 /* Not Found (e.g. calling "123456789") */:
            case 603 /* Decline (often used as hard reject / invalid / block, e.g calling "1") */: {
                message = _t(
                    "The number you dialed seems to be incorrect, unavailable, or blocked."
                );
                technicalExtra = _t(
                    "The number appears to be invalid. If you believe it is valid, check that your VoIP configuration is correct."
                );
                break;
            }
            case 488 /* Not Acceptable Here (Media / config issues) */: {
                message = _t("The call could not be established due to a configuration issue.");
                technicalExtra = _t(
                    "Configuration or compatibility issue (for example codecs or encryption)."
                );
                break;
            }
            case 486 /* Busy Here */:
            case 600 /* Busy Everywhere */: {
                message = _t("The person you are trying to contact is currently busy.");
                break;
            }
            default: {
                message = _t("Call rejected.");
            }
        }
        this.voip.triggerError({
            isBlocking: false,
            message,
            technical: _t("Received: %(code)s %(reason)s.", {
                code: response.message.statusCode,
                reason: response.message.reasonPhrase,
            }),
            technicalExtra,
        });
        this._updateStatuses("rejected");
    }

    _onCancel({ request }) {
        const reason = request.getHeader("Reason");
        if (/DESTINATION_OUT_OF_ORDER/i.test(reason)) {
            this._updateStatuses("rejected");
        } else if (
            /Call completed elsewhere/i.test(reason) ||
            /\bQ\.850\s*;\s*cause\s*=\s*26\b/i.test(reason)
        ) {
            // Another branch of the parallel call was answered
            this._updateStatuses("completed_elsewhere");
        } else if (
            /\bSIP\s*;\s*cause\s*=\s*603\b/i.test(reason) ||
            /\bQ\.850\s*;\s*cause\s*=\s*21\b/i.test(reason)
        ) {
            // Another registered SIP endpoint explicitly declined the call
            this._updateStatuses("rejected");
        } else {
            this._updateStatuses("missed");
        }
    }

    /**
     * Triggered when SIP.js makes a SessionDescriptionHandler for the session.
     *
     * @param {import("sip.js").Web.SessionDescriptionHandler} sessionDescriptionHandler
     */
    _onSessionDescriptionHandler(sessionDescriptionHandler) {
        this.onSessionDescriptionHandler(
            sessionDescriptionHandler,
            this.direction,
            this._onRemoteTrackAdded.bind(this),
            this._onLocalTrackUpdated.bind(this)
        );
    }

    /**
     * Triggered when the state of the SIP.js session changes to Established.
     */
    _onSessionEstablished() {
        this._wasEstablished = true;

        if (this._isOnHold) {
            this._requestHold(true);
        }

        if (this.voip.config.recordingPolicy !== "disabled") {
            this.setupRecorder();
        }

        this._updateStatuses("ongoing");

        this._startTimer();

        this.ringtone.stop();

        this.onSessionStateEstablished();
    }

    /**
     * Triggered when the state of the SIP.js session changes to Establishing.
     */
    _onSessionEstablishing() {
        if (this.direction === "outgoing") {
            this.ringtone.play("dial");
        } else {
            this.onIncomingRingtoneRequested();
        }
    }

    /** @param {import("sip.js").SessionState} newState */
    _onStateChanged(newState) {
        delete this._outgoingInviteIsRinging;
        switch (newState) {
            case SIP.SessionState.Establishing:
                this._onSessionEstablishing();
                break;
            case SIP.SessionState.Established:
                this._onSessionEstablished();
                break;
            case SIP.SessionState.Terminated: {
                this._onSessionTerminated();
                break;
            }
        }
        this.voip.bus.trigger("session_changed");
    }

    _startTimer() {
        this.timer = proxy({});
        // start_date is only available for device transfer; otherwise use
        // client time to avoid clock skew with the server.
        const timerStart = this.call?.start_date || luxon.DateTime.now();
        const computeDuration = () => {
            this.timer.time = Math.floor((luxon.DateTime.now() - timerStart) / 1000);
        };
        computeDuration();
        this.timer.interval = setInterval(computeDuration, 1000);
    }

    _stopTimer() {
        if (this.timer) {
            clearInterval(this.timer.interval);
            delete this.timer.interval;
        }
    }

    /**
     * Triggered when the state of the SIP.js session changes to Terminated.
     */
    _onSessionTerminated() {
        if (this._wasEstablished) {
            this._updateStatuses("terminated");
        } else if (this.direction === "incoming" && !this._inFinalState && !this._isRejecting) {
            // SIP.js terminates unanswered invitations when its no-answer
            // timer expires without triggering the cancellation delegate.
            this._updateStatuses("missed");
        }

        this._stopTimer();

        this.ringtone.stop();
        this.onSessionStateTerminated();

        this.stopRecorders();
    }

    /**
     * Requests the remote peer to put the session on hold / resume it.
     *
     * @param {boolean} state `true` to put on hold, `false` to resume.
     */
    async _requestHold(state) {
        if (!this.isOngoing) {
            // Session not yet established — just track the state without SIP signaling
            this._isOnHold = state;
            return;
        }
        try {
            await this.__sipJsSession.invite({
                requestDelegate: {
                    onAccept: () => {
                        this._isOnHold = state;
                        this._applyCallStateToTracks();
                    },
                },
                sessionDescriptionHandlerOptions: {
                    hold: state,
                },
            });
            this.voip.resolveError();
        } catch (error) {
            console.error(error);
            this.voip.triggerError({
                isBlocking: false,
                message:
                    state === true
                        ? _t("Couldn't put the call on hold.")
                        : _t("Couldn't resume the call."),
                technical: error.message,
            });
        }
    }

    /**
     * Determines if the media type for the audio is SRTP-DTLS.
     *
     * WebRTC mandates the use of "SRTP-DTLS", which means that RTP datagrams
     * must be encrypted using TLS (DTLS).
     *
     * Note that communication could still work with a "plain RTC" media type,
     * as long as the DTLS fingerprint is included.
     *
     * @returns {boolean}
     */
    _hasSrtpDtlsMediaType() {
        const sdp = this.__sipJsSession.body;
        const fields = sdp.split(/\r?\n/);
        return fields.some(
            (field) => field.startsWith("m=audio") && field.includes("UDP/TLS/RTP/SAVPF")
        );
    }

    /**
     * Determines if the SDP contains the attributes required by DTLS.
     *
     * @returns {boolean}
     */
    _hasDtlsAttributes() {
        const sdp = this.__sipJsSession.body;
        const fields = sdp.split(/\r?\n/);
        let hasFingerprint = false;
        let hasSetup = false;
        for (const field of fields) {
            hasFingerprint ||= field.startsWith("a=fingerprint");
            hasSetup ||= field.startsWith("a=setup");
        }
        return hasFingerprint && hasSetup;
    }

    /**
     * @param {{promote?: boolean, suppressError?: boolean}} [options={}]
     * @returns {Promise<void>}
     */
    async accept({ promote = true, suppressError = true } = {}) {
        if (this.__sipJsSession.state !== SIP.SessionState.Initial) {
            // A single INVITE can be auto-answered from two correlation paths
            // (control handle and Odoo call id); the first one transitions the
            // session out of Initial, so any later accept is a no-op.
            return;
        }
        // The setTimeout is required to avoid a flickering when accepting the
        // call when the microphone is already enabled. The async operation
        // afterwards waits for the microphone being enabled + the call to be
        // initialized: so the delay used here is a best guess.
        const resolveMicError = this.voip.triggerError({
            message: _t("Please accept use of the microphone."),
            delay: 500,
        });
        try {
            await this.__sipJsSession.accept({
                sessionDescriptionHandlerOptions: {
                    constraints: { audio: true },
                },
            });
            if (promote) {
                this.voip.userAgent.promoteToFront(this.key);
            }
            resolveMicError();
        } catch (error) {
            resolveMicError();

            console.error(error);
            let technicalExtra = "";
            if (!this._hasSrtpDtlsMediaType()) {
                technicalExtra = _t(
                    "The DTLS fingerprint and/or setup is missing from the SDP. Verify that the VoIP provider is configured to use SRTP-DTLS."
                );
            } else if (!this._hasDtlsAttributes()) {
                technicalExtra = _t(
                    "It appears that the server may not be using the correct media type. Verify that the media type is correctly set to SRTP-DTLS."
                );
            }
            this.voip.triggerError({
                isBlocking: false,
                message: _t("An error occurred while attempting to answer the incoming call."),
                technical: `Error message: ${error.message}`,
                technicalExtra,
            });
            if (!suppressError) {
                throw error;
            }
        }
    }

    /** @returns {Promise<import("sip.js").Core.OutgoingByeRequest>} */
    bye() {
        return this.__sipJsSession.bye();
    }

    cancel() {
        this.cancelRequested = true;
        return this.__sipJsSession.cancel().then(() => {
            this._updateStatuses("aborted");
        });
    }

    async reject() {
        this._isRejecting = true;
        try {
            await this.__sipJsSession.reject({ statusCode: 603 });
            this._updateStatuses("rejected");
        } finally {
            this._isRejecting = false;
        }
    }

    /**
     * Terminates the session in a proper way depending on its current state.
     * Will either cancel, reject or send a bye.
     */
    async hangup() {
        switch (this.__sipJsSession.state) {
            case SIP.SessionState.Initial:
            case SIP.SessionState.Establishing:
                return this.direction === "incoming" ? this.reject() : this.cancel();
            case SIP.SessionState.Established:
                return this.bye();
        }
    }

    /**
     * @param {boolean} [willCallFromAnotherDevice=false]
     * @param {{requestDelegate?: import("sip.js").Core.OutgoingRequestDelegate}} [options={}]
     * @returns {Promise<import("sip.js").Core.OutgoingInviteRequest>}
     */
    invite(willCallFromAnotherDevice = false, options = {}) {
        return this.__sipJsSession.invite({
            requestDelegate: Object.assign({}, this.inviteRequestDelegate, options.requestDelegate),
            sessionDescriptionHandlerOptions: {
                // Handle the case where the outgoing call will be transferred
                // anyway, in which case we do not even need to check for the
                // microphone presence (and surely not fail if no microphone).
                // See requestMediaStreamForSIP.
                constraints: { audio: !willCallFromAnotherDevice },
            },
        });
    }

    /**
     * @param {import("sip.js").URI|import("sip.js").Session} referTo
     * @param {import("sip.js").SessionReferOptions} options
     * @return {Promise<import("sip.js").Core.OutgoingReferRequest>}
     */
    refer(referTo, options) {
        if (toRaw(referTo) instanceof Session) {
            referTo = referTo.__sipJsSession;
        }
        return this.__sipJsSession.refer(referTo, options);
    }

    /** @returns true if DTMF was successfully sent */
    sendDtmf(key) {
        return this.__sipJsSession.sessionDescriptionHandler?.sendDtmf(key);
    }

    _updateStatuses(state) {
        if (this._inFinalState) {
            console.error("Session already in final state");
            return;
        }
        if (this._wasEstablished && !["ongoing", "terminated"].includes(state)) {
            console.error("Session was established");
            return;
        }
        this._inFinalState = state !== "ongoing";
        this.status = state;
        this._updateCallState(state);
    }

    async _updateCallState(state) {
        if (this.skipServerUpdate) {
            return;
        }
        const at = luxon.DateTime.now();
        try {
            switch (state) {
                case "ongoing":
                    await this.callProm.then(() => this.call.start(at));
                    break;
                case "terminated":
                    await this.callProm.then(() => this.call.end(at));
                    break;
                case "missed":
                    await this.callProm.then(() => this.call.miss());
                    break;
                case "completed_elsewhere":
                    await this.callProm.then(() => this.call.completeElsewhere());
                    break;
                case "rejected":
                    await this.callProm.then(() => this.call.reject());
                    break;
                case "aborted":
                    await this.callProm.then(() => this.call.abort());
                    break;
            }
        } catch (error) {
            console.error(error);
        }
    }

    /**
     * Returns the options to be passed to the SessionRecorder.
     * Overridden in demo module.
     * @returns {Object}
     */
    _getRecordingUploadOptions() {
        return {
            is_production: true,
        };
    }

    /**
     * Initializes the session recorder. Should be done immediately after the call was established.
     * Works in both production and demo modes.
     */
    async setupRecorder() {
        if (this.recorder) {
            return;
        }

        await this.callProm;

        // Ensure the call didn't end while odoo was creating call record.
        if (this._inFinalState) {
            return;
        }

        const startImmediately = this.voip.config.recordingPolicy === "always";
        this.recorder = new SessionRecorder(
            this.__sipJsSession,
            this.call.id,
            startImmediately,
            this._getRecordingUploadOptions(),
            this.voip.env.services.notification
        );
        this._initializeRecorderTracks();
    }

    /**
     * Initializes the recorder with the tracks currently active in the session.
     * This is necessary because the recorder is often created after the
     * initial tracks have already been established, meaning it would miss the
     * initial 'onRemoteTrackAdded' or local track setup events.
     */
    _initializeRecorderTracks() {
        if (!this.recorder) {
            return;
        }
        this._initializeTracksFor(this.recorder);
    }

    /**
     * Feeds the currently active tracks into a specific recorder instance.
     *
     * @param {SessionRecorder} recorder
     */
    _initializeTracksFor(recorder) {
        const sessionDescriptionHandler = this.__sipJsSession.sessionDescriptionHandler;
        // 1. Catch up on the local microphone track
        const micSender = sessionDescriptionHandler?.peerConnection
            ?.getSenders()
            .find((sender) => sender.track?.kind === "audio");
        recorder.updateLocalTrack(micSender?.track);

        // 2. Catch up on the remote caller track
        const remoteTrack = sessionDescriptionHandler?.remoteMediaStream
            ?.getAudioTracks()
            .find((track) => track.readyState === "live");
        recorder.updateRemoteTrack(remoteTrack);
    }

    /**
     * Manually stops the session recorder(s).
     */
    stopRecorders() {
        this.recorder?.recordOff();
    }
}
