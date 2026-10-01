import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";

import { Session } from "@voip/core/web/session";
import { SessionRecorder } from "@voip/core/web/session_recorder";

patch(Session.prototype, {
    /** @override */
    _onSessionEstablished() {
        super._onSessionEstablished(...arguments);
        if (this.voip.transcriptionEnabled) {
            this.setupTranscriptionRecorder();
        }
    },

    /**
     * @override
     * Ensures the parallel STT recorder captures remote audio as it connects.
     */
    _onRemoteTrackAdded(ev) {
        super._onRemoteTrackAdded(...arguments);
        this.sttRecorder?.updateRemoteTrack(ev.track);
    },

    /**
     * @override
     * Ensures the parallel STT recorder stays in sync if the user swaps
     * their microphone mid-call.
     */
    _onLocalTrackUpdated(track) {
        super._onLocalTrackUpdated(...arguments);
        this.sttRecorder?.updateLocalTrack(track);
    },

    async setupTranscriptionRecorder() {
        if (this.sttRecorder) {
            return;
        }
        await this.callProm; // Ensure call record already exists
        if (this._inFinalState) { // Ensure the call didn't end already
            return;
        }

        if (this.__sipJsSession.isMock && !this.__sipJsSession._localStream) {
            this.voip.env.services.notification.add(
                _t("Cannot access audio recording device. Please allow it and try again."),
                { type: "warning" }
            );
            return;
        }

        // STT Recorder: Parallel, Always On, with AI flag
        this.sttRecorder = new SessionRecorder(
            this.__sipJsSession,
            this.call.id,
            true, // Start Immediately
            {
                is_stt: true,
                is_demo: this.voip.config.mode === "demo",
            },
            this.voip.env.services.notification
        );

        // Manually feed the current live tracks to the new recorder in case
        // the call was already in progress when the recorder started.
        this._initializeTracksFor(this.sttRecorder);
    },

    /** @override */
    async stopRecorders() {
        super.stopRecorders(...arguments);
        if (this.sttRecorder) {
            await this.sttRecorder._terminate();
            // Trigger transcription fire-and-forget
            rpc(
                "/ai/transcription/call",
                {
                    call_model: "voip.call",
                    call_id: this.call.id,
                },
                { silent: true }
            ).catch(() => {});
        }
    },
});

patch(SessionRecorder.prototype, {
    /** @override */
    _shouldUseCloudStorage(uploadOptions) {
        return super._shouldUseCloudStorage(...arguments) && !uploadOptions.is_stt;
    },
});
