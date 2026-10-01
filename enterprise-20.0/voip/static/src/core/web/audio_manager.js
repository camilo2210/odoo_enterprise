import { _t } from "@web/core/l10n/translation";
import { Mutex } from "@web/core/utils/concurrency";
import { debounce } from "@web/core/utils/timing";

/**
 * Returns a live audio track from a stream, if any.
 *
 * @param {?MediaStream} [stream]
 * @returns {?MediaStreamTrack}
 */
function getLiveAudioTrack(stream) {
    return stream?.getAudioTracks().find((track) => track.readyState === "live") || null;
}

/**
 * Stops a stream and all of its tracks.
 *
 * @param {MediaStream} stream
 */
function stopStream(stream) {
    stream.getTracks().forEach((track) => track.stop());
}

/**
 * Centralizes VoIP stream creation, microphone permissions, related stream
 * lifecycle, etc.
 *
 * Main ideas:
 * - Keep browser permission and device logic in one place so UserAgent focuses
 *   on SIP initialization, updates, etc.
 * - Request a fresh stream when the session can accept tracks.
 * - etc.
 */
export class AudioManager {
    /** @type {Voip} */
    voip;
    /** @type {Map<import("sip.js").Web.SessionDescriptionHandler, Object>} */
    _sdhToData = new Map();
    // Note: it would really make more sense to have a global ringtone service
    // as in the past, that the audio manager can just update as needed (output
    // device, ...). We probably never want two ringtones playing at the same
    // time anyway.
    /** @type {Set<Ringtone>} */
    _ringtones = new Set();
    /** @type {Mutex} */
    _deviceUpdateMutex = new Mutex();

    /**
     * @constructor
     * @param {Voip} voip
     */
    constructor(voip) {
        this.voip = voip;
        this.applyInputDeviceToSessions = debounce(this.applyInputDeviceToSessions, 100);
    }

    /**
     * Starts listening for devices and permissions changes and refreshes the
     * microphone status.
     *
     * @returns {Promise}
     */
    async setup() {
        navigator.mediaDevices?.addEventListener("devicechange", this._onDeviceChange.bind(this));
        const { rtc, settings } = this.voip.store;
        // pure change-reactions: the trailing refresh does the initial sync
        rtc.onChange(
            () => [rtc.microphonePermission],
            () => this._onPermissionChange(),
            { initialRun: false }
        );
        settings.onChange(
            () => [settings.audioInputDeviceId],
            () => this._onInputDeviceChoice(),
            { initialRun: false }
        );
        settings.onChange(
            () => [settings.audioOutputDeviceId],
            () => this._onOutputDeviceChoice(),
            { initialRun: false }
        );
        settings.onChange(
            () => [settings.ringtoneOutputDeviceId],
            () => this._onRingtoneOutputDeviceChoice(),
            { initialRun: false }
        );
        return this._refreshMicrophoneStatus();
    }

    /**
     * @param {import("sip.js").Web.SessionDescriptionHandler} sessionDescriptionHandler
     * @param {"incoming"|"outgoing"} direction
     * @param {Function} onRemoteTrackAdded
     * @param {Function} [onLocalTrackUpdated] - Callback run when microphone is updated
     */
    setupSessionDescriptionHandler(
        sessionDescriptionHandler,
        direction,
        onRemoteTrackAdded,
        onLocalTrackUpdated
    ) {
        const data = {
            direction: direction,
            onLocalTrackUpdated,
        };
        this._sdhToData.set(sessionDescriptionHandler, data);

        // Extends what happens when SIP.js will ask the session description
        // handler to close: perform our own cleaning afterwards.
        const originalClose = sessionDescriptionHandler.close;
        const cleanupSessionDescriptionHandler = this._cleanupSessionDescriptionHandler.bind(this);
        sessionDescriptionHandler.close = function (...args) {
            try {
                return originalClose.call(this, ...args);
            } finally {
                cleanupSessionDescriptionHandler(this);
            }
        };

        // Setup the remote audio
        const remoteAudio = new Audio();
        data.remoteAudio = remoteAudio;
        remoteAudio.srcObject = sessionDescriptionHandler.remoteMediaStream;
        sessionDescriptionHandler.remoteMediaStream.addEventListener("addtrack", (...args) => {
            onRemoteTrackAdded(...args);
            remoteAudio.play().catch((error) => console.warn("Browser prevented autoplay.", error));
        });

        // Setup the output device (the input device will be asked by SIP.js at
        // a later stage). Note that this is async and the setup here is
        // supposed to be synchronous, but it should not be a problem for the
        // stream track to be updated later without waiting for it.
        this.applyOutputDeviceToSession(sessionDescriptionHandler);
    }

    /**
     * @param {import("sip.js").Web.SessionDescriptionHandler} sessionDescriptionHandler
     */
    _cleanupSessionDescriptionHandler(sessionDescriptionHandler) {
        const data = this._sdhToData.get(sessionDescriptionHandler);
        this._sdhToData.delete(sessionDescriptionHandler);

        // Explicitly reset the src and stops playback of the remote audio to
        // ensure that it can be garbage-collected.
        const remoteAudio = data.remoteAudio;
        remoteAudio.pause();
        remoteAudio.srcObject = null;
        remoteAudio.load();

        // Clean up the source audio (which could be empty (`makeEmptyStream`)
        // but would need explicit cleaning either way).
        data.cleanup?.();
    }

    /**
     * Refreshes the microphone status, based on devices and permissions status.
     *
     * @returns {Promise}
     */
    async _refreshMicrophoneStatus() {
        const devices = await navigator.mediaDevices?.enumerateDevices();
        this._hasAudioInput = devices?.some((device) => device.kind === "audioinput");

        const permissionState = this.voip.store.rtc.microphonePermission;
        if (!permissionState) {
            this._setMicrophoneError({ technical: "NotSupportedError" });
            return;
        }
        if (!this._hasAudioInput) {
            this._setMicrophoneError({ technical: "NotFoundError" });
            return;
        }

        switch (permissionState) {
            case "granted": {
                this._unsetMicrophoneError();
                return;
            }
            case "denied": {
                this._setMicrophoneError({ technical: "NotAllowedError" });
                return;
            }
            case "prompt": {
                this._setMicrophoneError({
                    message: _t("Microphone access has not been granted yet."),
                    technical: "NotAllowedError",
                });
                return;
            }
            default: {
                this._setMicrophoneError({ technical: "NotFoundError" });
                return;
            }
        }
    }

    /**
     * Mutex-protected version of {@see _applyInputDeviceToSessions}.
     *
     * We debounce the calls to this since it makes sense but also to optimize
     * the basic call flow: this can be called after any permission change (see
     * _onPermissionChange) (e.g. if the user goes in their browser settings by
     * themselves, in which case we don't want to force error display)...
     * However, the permission change can also happen during the use of the
     * discuss dialog, in which case we will end up calling this too, with force
     * error display. So the debounce allows to wait to see if that happens.
     */
    async applyInputDeviceToSessions(forceErrorDisplay, forceStreamRequest) {
        return this._deviceUpdateMutex.exec(() => this._applyInputDeviceToSessions(...arguments));
    }

    /**
     * Requests microphone access from the user and applies the stream to known
     * sessions when possible.
     *
     * @param {boolean} forceErrorDisplay - Indicates if a message should be
     *  shown if the microphone is already blocked (as the browser won't allow
     *  to ask again in that case).
     * @param {boolean} [forceStreamRequest=false] - Indicates if a new stream
     *  should be requested even if a current live track exists.
     * @returns {Promise}
     */
    async _applyInputDeviceToSessions(forceErrorDisplay, forceStreamRequest = false) {
        const sessionDescriptionHandlers = [...this._sdhToData.keys()];
        const senders = sessionDescriptionHandlers
            .map((sessionDescriptionHandler) => ({
                sessionDescriptionHandler,
                sender: sessionDescriptionHandler.peerConnection
                    ?.getSenders()
                    .find((item) => item.track?.kind === "audio"),
            }))
            .filter((data) => Boolean(data.sender));

        // First try to re-apply the last set up audio track to current known
        // sessions. If it is considered a success (probably because it was
        // already applied and nothing had to be done), no need to do anything:
        // we assume the rest of them were updated with clones in the past.
        if (!forceStreamRequest) {
            const currentTrack = getLiveAudioTrack(this._lastMadeStream);
            if (currentTrack && senders.some((data) => data.sender.track === currentTrack)) {
                return;
            }
        }

        // Otherwise, create a new request for the microphone and apply the new
        // stream to potentially active sessions.
        let stream;
        try {
            stream = await this.requestMediaStream(forceErrorDisplay);
        } catch {
            // Error display handled by requestMediaStream
            return;
        }

        // Apply stream to sessions
        const audioTrack = getLiveAudioTrack(stream);
        const applyProms = senders.map(async (data) => {
            const sessionAudioTrack = audioTrack.clone();
            sessionAudioTrack.enabled = Boolean(data.sender.track?.enabled);
            try {
                await data.sender.replaceTrack(sessionAudioTrack);
            } catch (error) {
                sessionAudioTrack.stop();
                console.error("Failed to update microphone track:", error);
                return null;
            }
            return {
                sessionDescriptionHandler: data.sessionDescriptionHandler,
                audioTrack: sessionAudioTrack,
            };
        });
        const allApplied = (await Promise.all(applyProms)).filter(Boolean);

        // Notify active sessions (and their recorders) about microphone change
        allApplied.forEach(({ sessionDescriptionHandler, audioTrack }) => {
            this._sdhToData.get(sessionDescriptionHandler)?.onLocalTrackUpdated?.(audioTrack);
        });

        // If microphone was requested outside of a pending session (or the
        // pending session(s) is not accepting audio tracks at the moment), we
        // stop the stream. Once a session will be valid, the next call to this
        // function will create a new stream without asking the user for the
        // permission again.
        if (!allApplied.length) {
            stopStream(stream);
            return;
        }

        // Otherwise, make sure each individual track can properly be cleaned up
        // and the main source cleaned up once all cloned tracks have been.
        let nbAppliedSources = allApplied.length;
        let sourceStreamStopped = false;
        const maybeStopSourceStream = () => {
            if (sourceStreamStopped || --nbAppliedSources > 0) {
                return;
            }
            sourceStreamStopped = true;
            stopStream(stream);
        };
        for (const { sessionDescriptionHandler, audioTrack: sessionAudioTrack } of allApplied) {
            let sessionSourceWasCleaned = false;
            this._setSourceCleanup(sessionDescriptionHandler, () => {
                if (sessionSourceWasCleaned) {
                    return;
                }
                sessionSourceWasCleaned = true;
                sessionAudioTrack.stop();
                maybeStopSourceStream();
            });
        }
    }

    /**
     * Creates the media source that will serve as the local media stream (i.e.
     * the recording of the user's microphone) used by SIP.js.
     *
     * @see {import("sip.js").Web.defaultMediaStreamFactory}
     * @throws {DOMException} see MediaDevices.getUserMedia
     * @returns {Promise<MediaStream>}
     */
    async requestMediaStreamForSIP(constraints, sessionDescriptionHandler) {
        function makeEmptyStream() {
            const ctx = new window.AudioContext();
            const destination = ctx.createMediaStreamDestination();
            const stream = destination.stream;
            const cleanup = () => {
                if (ctx.state === "closed") {
                    return;
                }
                stopStream(stream);
                ctx.close();
            };
            return { stream, cleanup };
        }

        let stream, cleanup;
        // It is supposed we never ask for video
        if (!constraints.audio) {
            // E.g. see willCallFromAnotherDevice
            ({ stream, cleanup } = makeEmptyStream());
        } else {
            // Audio device requested.

            // We want the discuss' permission dialog only in one case:
            // permission are not yet granted or denied and it is an outgoing
            // call. For incoming, we want the user to be able to react quicker.
            // In the other cases, we don't want to disrupt the process of the
            // call initialization.
            const shouldBrowserPrompt = this.voip.store.rtc.microphonePermission === "prompt";
            if (
                shouldBrowserPrompt &&
                this._sdhToData.get(sessionDescriptionHandler).direction === "outgoing"
            ) {
                const dismissed = await new Promise((resolve) => {
                    // Note that this is a clone since this is a getter
                    const configuration = this.voip.softphone.audioPermissionDialogConfiguration;
                    const originalOnClose = configuration.options.onClose;
                    configuration.options.onClose = (...args) => {
                        originalOnClose(...args);
                        resolve(Boolean(args[0]?.dismiss));
                    };
                    this.voip.store.rtc.showMediaPermissionDialog("microphone", configuration);
                });
                if (dismissed) {
                    ({ stream, cleanup } = makeEmptyStream());
                }
            }
            // In any case, we allow that request to fail and the call to
            // proceed anyway, e.g. in case the user just wants to transfer the
            // call once it starts. Notice that we show errors only if the user
            // is supposed to be prompted for permission and there is an input
            // device, otherwise we rely on the fact the user has an indication
            // that the microphone is not configured.
            const forceErrorDisplay = shouldBrowserPrompt && this._hasAudioInput;
            if (!stream) {
                try {
                    stream = await this.requestMediaStream(forceErrorDisplay);
                    cleanup = () => stopStream(stream);
                } catch {
                    // Error display handled by requestMediaStream
                    ({ stream, cleanup } = makeEmptyStream());
                }
            }
        }
        this._setSourceCleanup(sessionDescriptionHandler, cleanup);
        const data = this._sdhToData.get(sessionDescriptionHandler);
        data?.onLocalTrackUpdated?.(getLiveAudioTrack(stream));

        return stream;
    }

    /**
     * Requests microphone access, notify an error if not possible, otherwise
     * returns the resulting stream.
     *
     * @throws {DOMException} If microphone access fails or no live audio track
     * @param {boolean} forceErrorDisplay - Indicates if a message should be
     *  shown if the microphone is already blocked (as the browser won't allow
     *  to ask again in that case).
     * @returns {Promise<MediaStream>}
     */
    async requestMediaStream(forceErrorDisplay) {
        let stream, error;
        try {
            stream = await navigator.mediaDevices.getUserMedia({
                audio: this.voip.store.settings.audioConstraints,
            });
            this._lastMadeStream = stream;
        } catch (err) {
            error = err;
        }
        // Might not be entirely needed but avoids a potentially invalid stream
        // being created and sent to SIP.js
        if (stream && !getLiveAudioTrack(stream)) {
            stopStream(stream);
            error = new DOMException(
                "No live audio track returned by getUserMedia.",
                "NotReadableError"
            );
        }
        if (error) {
            this._setMicrophoneError(
                {
                    technical: error.name,
                    technicalExtra: error.message,
                },
                forceErrorDisplay
            );
            throw error;
        }
        this._unsetMicrophoneError();
        return stream;
    }

    /**
     * Sets the new active stream used by session(s). The old one will be
     * stopped first for the same session description handler, if any.
     *
     * @param {import("sip.js").Web.SessionDescriptionHandler} sessionDescriptionHandler
     * @param {Function} cleanup
     */
    _setSourceCleanup(sessionDescriptionHandler, cleanup) {
        const data = this._sdhToData.get(sessionDescriptionHandler);

        // First clean the potential old cleanup
        data.cleanup?.();

        data.cleanup = () => {
            try {
                cleanup();
            } catch (error) {
                console.error("Failed to cleanup audio stream:", error);
            }
        };
    }

    /**
     * Updates the VoIP microphone error state. This also cleans up all source
     * streams, assuming a microphone error should prevent calls to continue
     * without first fixing the error.
     *
     * @param {Object} [params]
     * @param {string} [params.message]
     * @param {string} [params.technical]
     * @param {string} [params.technicalExtra]
     * @param {string} [forceDisplay=false] - Indicates if a message should be
     *  shown (e.g. when the error if for example because the microphone is
     *  already blocked and the browser won't allow to ask again)
     */
    _setMicrophoneError({ message, technical, technicalExtra } = {}, forceDisplay = false) {
        // Stops any stored stream and clears internal state. Note that for a
        // "basic" MediaStream that was requested by SIP.js using the
        // `MediaStreamFactory`, cleaning is supposed to be done by SIP.js
        // automatically. But as soon as this audio manager messes with
        // switching device and permissions during a call, cleaning up
        // explicitly is better, if not required.
        for (const data of this._sdhToData.values()) {
            data.cleanup?.();
            delete data.cleanup;
        }

        // Prepare the message, at minimum as a tooltip for the mic indicator
        // but also as a forced visible error if required.
        if (!message) {
            switch (technical) {
                case "NotAllowedError": {
                    message = _t(
                        "Cannot access audio recording device. If you have denied access to your microphone, please allow it and try again. Otherwise, make sure that this website is running over HTTPS and that your browser is not set to deny access to media devices."
                    );
                    break;
                }
                case "NotFoundError": {
                    message = _t(
                        "No audio recording device available. The application requires a microphone in order to be used."
                    );
                    break;
                }
                case "NotReadableError": {
                    message = _t(
                        "A hardware error has occurred while trying to access the audio recording device. Please ensure that your computer is up to date (e.g. the drivers) and try again."
                    );
                    break;
                }
                case "NotSupportedError": {
                    message = _t("Microphone access is not supported by this browser.");
                    break;
                }
                default: {
                    message = _t("An error occurred involving the audio recording device.");
                    break;
                }
            }
        }
        if (forceDisplay) {
            this._unsetMicrophoneError();
            this._cleanPreviousMicrophoneError = this.voip.triggerError({
                isBlocking: false,
                message: message,
                technical: technical,
                technicalExtra: technicalExtra,
            });
        }
        this.voip.microphoneError = message;
    }

    /**
     * Removes any VoIP microphone error state previously set.
     */
    _unsetMicrophoneError() {
        if (this._cleanPreviousMicrophoneError) {
            this._cleanPreviousMicrophoneError();
            this._cleanPreviousMicrophoneError = null;
        }
        this.voip.microphoneError = null;
    }

    /**
     * Applies the preferred call output device to known sessions when possible
     * (this is mutex-protected).
     *
     * @returns {Promise}
     */
    async applyOutputDeviceToSessions() {
        const proms = [...this._sdhToData.keys()].map((sessionDescriptionHandler) =>
            this.applyOutputDeviceToSession(sessionDescriptionHandler)
        );
        return Promise.all(proms);
    }

    /**
     * Registers a ringtone so it follows output device changes for its entire
     * session.
     *
     * @param {Ringtone} ringtone
     * @returns {Promise}
     */
    registerRingtone(ringtone) {
        this._ringtones.add(ringtone);
        return this.applyOutputDeviceToRingtone(ringtone);
    }

    /** @param {Ringtone} ringtone */
    unregisterRingtone(ringtone) {
        this._ringtones.delete(ringtone);
    }

    /**
     * Mutex-protected version of {@see _applyOutputDeviceToSession}.
     */
    async applyOutputDeviceToSession(sessionDescriptionHandler) {
        return this._deviceUpdateMutex.exec(() => this._applyOutputDeviceToSession(...arguments));
    }

    /**
     * Applies the preferred output device to a given session when possible.
     *
     * @param {import("sip.js").Web.SessionDescriptionHandler} sessionDescriptionHandler
     * @returns {Promise}
     */
    async _applyOutputDeviceToSession(sessionDescriptionHandler) {
        if (!this._sdhToData.has(sessionDescriptionHandler)) {
            // Could happen if the session was quickly closed after asking for
            // this function to be called (as done asynchronously).
            return;
        }
        const { remoteAudio } = this._sdhToData.get(sessionDescriptionHandler);
        return this._applyOutputDeviceToAudioElement(remoteAudio, "audioOutputDeviceId");
    }

    /**
     * Applies the preferred ringtone output device to known ringtones when
     * possible (this is mutex-protected).
     *
     * @returns {Promise}
     */
    async applyOutputDeviceToRingtones() {
        const proms = [...this._ringtones].map((ringtone) =>
            this.applyOutputDeviceToRingtone(ringtone)
        );
        return Promise.all(proms);
    }

    /**
     * Mutex-protected version of {@see _applyOutputDeviceToRingtone}.
     *
     * @param {Ringtone} ringtone
     * @returns {Promise}
     */
    async applyOutputDeviceToRingtone(ringtone) {
        return this._deviceUpdateMutex.exec(() => this._applyOutputDeviceToRingtone(...arguments));
    }

    /**
     * Applies the preferred output device to a given ringtone when possible.
     *
     * @param {Ringtone} ringtone
     * @returns {Promise}
     */
    async _applyOutputDeviceToRingtone(ringtone) {
        if (!this._ringtones.has(ringtone)) {
            // Could happen if the session was quickly removed after asking for
            // this function to be called (as done asynchronously).
            return;
        }
        return this._applyOutputDeviceToAudioElement(ringtone.audio, "ringtoneOutputDeviceId");
    }

    /**
     * Applies an output device setting to an audio element.
     *
     * @param {HTMLAudioElement} audio
     * @param {"audioOutputDeviceId"|"ringtoneOutputDeviceId"} settingName
     * @returns {Promise}
     */
    async _applyOutputDeviceToAudioElement(audio, settingName) {
        if (typeof HTMLAudioElement.prototype.setSinkId !== "function") {
            // Should not happen: normally only not supported on mobile devices
            // in which case we should not have output device selection; but
            // important to know about.
            console.warn("Output device selection not supported");
            return;
        }

        const deviceId = this.voip.store.settings[settingName] || "";
        try {
            await audio.setSinkId(deviceId);
        } catch (error) {
            console.info("Failed to update audio output device:", error);
            this.voip.store.settings[settingName] = "";
        }
    }

    /**
     * Handles device list changes.
     */
    _onDeviceChange() {
        this._refreshMicrophoneStatus();
        // Note that on device change, we don't automatically add a new stream
        // to current sessions: we wait for the user to ask.
    }

    /**
     * Handles permission state changes.
     */
    _onPermissionChange() {
        this._refreshMicrophoneStatus();
        if (this.voip.store.rtc.microphonePermission === "granted" && this._sdhToData.size) {
            this.applyInputDeviceToSessions(false);
        }
    }

    /**
     * Handles audio input device selection changes.
     */
    _onInputDeviceChoice(forceStreamRequest = false) {
        this._refreshMicrophoneStatus();
        if (this._sdhToData.size) {
            this.applyInputDeviceToSessions(false, true);
        }
    }

    /**
     * Handles audio output device selection changes.
     *
     * Note: output device selection is known to be capricious and browser
     * dependent (e.g. on Firefox sometimes output devices are not properly
     * listed, on Chrome sometimes switching output fails until we change the
     * output on the OS side, ...). We try to mitigate those issues as much as
     * possible (e.g. see `setSinkId` in `_applyOutputDeviceToSession`).
     */
    _onOutputDeviceChoice() {
        this.applyOutputDeviceToSessions();
    }

    /**
     * Handles ringtone output device selection changes.
     */
    _onRingtoneOutputDeviceChoice() {
        this.applyOutputDeviceToRingtones();
    }
}
