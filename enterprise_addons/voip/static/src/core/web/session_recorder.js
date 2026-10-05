import { proxy, computed } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { fixWebmDuration } from "./fix_webm_duration";

/**
 * Handles the recording of a VoIP session by mixing local and remote audio.
 *
 * The recorder instance is designed to persist for the entire duration of a call.
 * "Starting" or "Stopping" the recording from the user interface is implemented
 * by starting or stopping the MediaRecorder instances, which ensures that the
 * resulting audio artifacts are correctly timed within the call's timeline.
 */
export class SessionRecorder {
    /** @type {Map<string, string>} */
    static EXTENSION_BY_MIMETYPE = new Map([
        ["audio/aac", "aac"],
        ["audio/mpeg", "mp3"],
        ["audio/mp4", "m4a"],
        ["audio/ogg", "ogg"],
        ["audio/wav", "wav"],
        ["audio/webm", "webm"],
    ]);

    /**
     * Maps a SessionRecorder instance to a Set of its active upload promises.
     * This acts as the single source of truth for tracking uploads and managing
     * the lifecycle of recorder instances.
     * @type {Map<SessionRecorder, Set<Promise<Response>>>}
     */
    static uploadsByRecorder = proxy(new Map());

    /**
     * Is ANY SessionRecorder is currently uploading
     */
    static isUploadInProgress = computed(() => {
        for (const promises of SessionRecorder.uploadsByRecorder.values()) {
            if (promises.size > 0) {
                return true;
            }
        }
        return false;
    });

    /**
     * Most preferred types come first.
     * @type {string[]}
     */
    static PREFERRED_MIMETYPES = [
        "audio/webm;codecs=opus",
        "audio/ogg;codecs=opus",
        "audio/mp4;codecs=mp4a.40.2", // Older Safari-friendly fallback
        "audio/mp4", // Older Safari-friendly fallback
        "audio/wav", // uncompressed, last resort
    ];
    static CHUNK_DURATION_MS = 60000;

    /** @type {AudioContext|null} Audio processing graph for this recorder */
    _audioContext;
    /** @type {GainNode|null} Volume slider for the microphone, needed when the local track changes */
    _localGain;
    /** @type {GainNode|null} Volume slider for the peer audio, needed when the remote track changes */
    _remoteGain;
    /** @type {AudioNode|null} Current microphone feed, needed to unplug it before switching tracks */
    _localSource;
    /** @type {AudioNode|null} Current peer feed, needed to unplug it before switching track. */
    _remoteSource;
    /**
     * When set, the recorder starts a new audio chunk
     * as soon as recording of the current chunk has finished
     * @type {boolean}
     */
    _isRecordingActive = false;
    /** @type {boolean} Guards against concurrent termination loops */
    _isTerminating = false;
    /** @type {Promise|null} Resolved when the latest MediaRecorder 'stop' event has been processed */
    _pendingStopEvent = null;
    /** @type {Function|null} Resolver for the _pendingStopEvent promise */
    _resolvePendingStopEvent = null;

    /**
     * Sets up a recorder for the given SIP session.
     *
     * @constructor
     * @param {import("sip.js").Session} sipSession
     * @param {number} callId
     * @param {boolean} [startImmediately=false]
     * @param {Object} [uploadOptions={}]
     * @param {boolean} [uploadOptions.is_production] If true the chunk should use Cloud Storage if enabled
     * @param {Object} [notification]
     */
    constructor(
        sipSession,
        callId,
        startImmediately = false,
        uploadOptions = {},
        notification = null
    ) {
        this.callId = callId;
        this.uploadOptions = uploadOptions;
        this.notification = notification;

        this._audioContext = new AudioContext();
        const mergedAudio = new MediaStreamAudioDestinationNode(this._audioContext, {
            channelCount: 1,
            channelCountMode: "explicit",
            channelInterpretation: "speakers",
        });

        // Setup Gains to allow mixing without clipping
        const gain = 1 / Math.sqrt(2);
        this._localGain = new GainNode(this._audioContext, { gain });
        this._remoteGain = new GainNode(this._audioContext, { gain });
        this._localGain.connect(mergedAudio);
        this._remoteGain.connect(mergedAudio);

        this._stream = mergedAudio.stream;

        const mimeType = this.outputMimeType;
        const ua = navigator.userAgent;
        const isWebKit = /AppleWebKit/.test(ua) && !/Chrome|Chromium|Edg|OPR/i.test(ua);
        const mediaRecorderOptions = {
            // Chrome/Firefox (Opus) handle 8kbps fine (G.729 VoIP standard).
            // WebKit (Safari/iOS) uses AAC, which fails/records silence at 8kbps. 32kbps is its safe minimum.
            audioBitsPerSecond: isWebKit ? 32000 : 8000,
            mimeType,
        };

        this._recorder = new MediaRecorder(this._stream, mediaRecorderOptions);
        this._startTime = Date.now(); // zero-point for aligning chunks times

        // Initialize the upload tracking Set for this specific recording instance
        SessionRecorder.uploadsByRecorder.set(this, new Set());

        this._setupRecorder(this._recorder, this.uploadOptions);

        if (sipSession) {
            sipSession.stateChange.addListener((state) => {
                if (state === "Terminated") {
                    this._terminate();
                }
            });
        }

        if (startImmediately) {
            this.recordOn();
        }
    }

    get isRecording() {
        return this._isRecordingActive;
    }

    /** Stops audio capture and uploads it */
    recordOff() {
        this._isRecordingActive = false;
        if (this._recorder.state !== "inactive") {
            this._recorder.stop();
        }
        clearTimeout(this._chunkTimer);
    }

    /** Starts audio capture, periodically uploading it*/
    recordOn() {
        if (!this._isRecordingActive && !this._isTerminating) {
            this._isRecordingActive = true;
            this._startRecorder();
        }
    }

    /**
     * Private helper to start the hardware recorder.
     * This creates the synchronization barrier BEFORE the hardware starts
     * to eliminate the timing gap during termination.
     */
    _startRecorder() {
        if (this._recorder.state !== "inactive") {
            return;
        }
        const { promise, resolve } = Promise.withResolvers();
        this._pendingStopEvent = promise;
        this._resolvePendingStopEvent = resolve;
        this._recorder.start();
        this._chunkTimer = setTimeout(() => {
            if (this._recorder.state !== "inactive") {
                this._recorder.stop();
            }
        }, SessionRecorder.CHUNK_DURATION_MS);
    }

    /**
     * Unplugs previous microphone, plugs in the new one
     * @param {MediaStreamTrack} track
     */
    updateLocalTrack(track) {
        if (this._localSource) {
            this._localSource.disconnect();
        }
        if (track && track.readyState === "live") {
            this._localSource = this._audioContext.createMediaStreamSource(
                new MediaStream([track])
            );
            this._localSource.connect(this._localGain);
        }
    }

    /**
     * Unplugs the remote track being recorded plugging in the new one
     * @param {MediaStreamTrack} track
     */
    updateRemoteTrack(track) {
        if (this._remoteSource) {
            this._remoteSource.disconnect();
        }
        if (track && track.readyState === "live") {
            this._remoteSource = this._audioContext.createMediaStreamSource(
                new MediaStream([track])
            );
            this._remoteSource.connect(this._remoteGain);
        }
    }

    /**
     * Sets up the MediaRecorder event listeners.
     * The recording cycle relies on a strict sequential lifecycle:
     * 1 start - marks the beginning of a new chunk
     * 2 dataavailable - captures the end time of the chunk
     * 3 stop restarts the recorder, triggering the next 'start' event
     * This sequence naturally prevents chunks from overlapping in time
     * @param {MediaRecorder} recorder
     * @param {Object} uploadOptions
     */
    _setupRecorder(recorder, uploadOptions = {}) {
        recorder._chunkStartTime = 0;

        recorder.addEventListener("start", () => {
            // Chunk starts NOW relative to call start
            recorder._chunkStartTime = Date.now() - this._startTime;
        });

        recorder.addEventListener("dataavailable", (ev) => {
            if (ev.data && ev.data.size > 0) {
                // WARNING: Do not use await before calculating timestamps!
                // Keeping this synchronous ensures the event loop locks endMs
                // before executing the stop event, preventing overlap
                const now = Date.now();
                const callElapsedTimeMs = now - this._startTime;

                const startMs = recorder._chunkStartTime;
                const endMs = callElapsedTimeMs;

                this._uploadChunk(ev.data, startMs, endMs, uploadOptions);
            }
        });

        recorder.addEventListener("stop", () => {
            this._resolvePendingStopEvent?.();
            if (this._isRecordingActive && !this._isTerminating) {
                this._startRecorder();
            }
        });

        recorder.addEventListener("error", (ev) => {
            console.error("SessionRecorder Error:", ev.error);
            this._terminate();
        });
    }

    /**
     * Public-ish method to upload a chunk, manages upload promises
     * @param {Blob} blob
     * @param {number} startMs
     * @param {number} endMs
     * @param {Object} [uploadOptions={}]
     * @returns {Promise<void>}
     */
    _uploadChunk(blob, startMs, endMs, uploadOptions = {}) {
        const promise = this._performUpload(blob, startMs, endMs, uploadOptions);
        const instancePromises = SessionRecorder.uploadsByRecorder.get(this);
        if (instancePromises) {
            instancePromises.add(promise);
            promise.finally(() => {
                instancePromises.delete(promise);
            });
        }
        return promise;
    }

    /**
     * Uploads a recorded audio chunk to the server or directly to Cloud Storage.
     * @param {Blob} blob The recorded audio data chunk.
     * @param {number} startMs The start time of this chunk relative to the call start, in milliseconds.
     * @param {number} endMs The end time of this chunk relative to the call start, in milliseconds.
     * @param {Object} [uploadOptions={}] Additional payload data appended to the server request.
     * @returns {Promise<void>}
     */
    async _performUpload(blob, startMs, endMs, uploadOptions = {}) {
        let isCloudStorage = false;
        let fileToUpload = blob;
        const filename = `chunk_${startMs}.${this.outputFileExtension}`;

        // Browsers' MediaRecorder (especially Firefox) generates WebM files without Duration, required for seeking
        if (blob.type.includes("webm")) {
            const durationMs = endMs - startMs;
            blob = await new Promise((resolve) => {
                fixWebmDuration(blob, durationMs, (fixedBlob) => {
                    resolve(fixedBlob || blob);
                });
            });
            fileToUpload = blob;
        }

        if (this._shouldUseCloudStorage(uploadOptions)) {
            isCloudStorage = true;
            fileToUpload = new File([new Blob([])], filename, { type: blob.type });
        }

        const formData = new FormData();
        formData.append("csrf_token", odoo.csrf_token);
        formData.append("ufile", fileToUpload, filename);
        formData.append("start_ms", startMs);
        formData.append("end_ms", endMs);
        if (isCloudStorage) {
            formData.append("cloud_storage", "true");
        }
        for (const [key, value] of Object.entries(uploadOptions)) {
            formData.append(key, value);
        }
        const url = `/voip/upload_recording/${this.callId}`;
        const promise = fetch(url, { method: "POST", body: formData });

        try {
            const response = await promise;
            if (!response.ok) {
                this.notification?.add(_t("Failed to upload recording"), { type: "danger" });
            } else if (isCloudStorage) {
                const data = await response.json();
                if (data.error) {
                    this.notification?.add(data.error, { type: "danger" });
                } else if (data.upload_info) {
                    const uploadInfo = data.upload_info;
                    const xhr = new window.XMLHttpRequest();
                    const cloudUploadPromise = new Promise((resolve, reject) => {
                        xhr.open(uploadInfo.method, uploadInfo.url);
                        const headers = Object.entries(uploadInfo.headers || {});
                        for (const [key, value] of headers) {
                            xhr.setRequestHeader(key, value);
                        }
                        xhr.onload = () => {
                            const isStatusOk = xhr.status === uploadInfo.response_status;
                            if (xhr.status === 403 || !isStatusOk) {
                                console.error("Cloud storage error", xhr.status);
                                reject(new Error("Cloud storage error"));
                                return;
                            }
                            resolve();
                        };
                        xhr.onerror = () => reject(new Error("Cloud storage network error"));
                        xhr.onabort = () => reject(new Error("Cloud storage upload aborted"));
                    });

                    xhr.send(blob);

                    await cloudUploadPromise;
                }
            }
        } catch (err) {
            console.error("SessionRecorder Chunk upload error", err);
        }
    }

    /**
     * Determines if the given audio chunk should be uploaded to Cloud Storage
     * @param {Object} uploadOptions
     * @returns {boolean}
     */
    _shouldUseCloudStorage(uploadOptions) {
        return uploadOptions.is_production;
    }

    /** @returns {string} */
    get outputFileExtension() {
        const mimeType = this._recorder.mimeType.split(";")[0];
        return SessionRecorder.EXTENSION_BY_MIMETYPE.get(mimeType) ?? "bin";
    }

    /** @returns {string} */
    get outputMimeType() {
        for (const mimeType of SessionRecorder.PREFERRED_MIMETYPES) {
            if (MediaRecorder.isTypeSupported(mimeType)) {
                return mimeType;
            }
        }
        return ""; // let browser pick
    }

    /**
     * Terminates the recorder and handles deferred Map cleanup
     * Ensures complete audio is on the server before the recorder is destroyed
     */
    async _terminate() {
        if (this._isTerminating) {
            return;
        }
        this._isTerminating = true;
        this._isRecordingActive = false;

        if (this._recorder.state !== "inactive") {
            this._recorder.stop();
        }

        // Guarding against edgecase of terminate running before the
        // 'dataavailable' handler registers the uploadPromise
        if (this._pendingStopEvent) {
            await Promise.race([
                this._pendingStopEvent,
                new Promise((resolve) => setTimeout(resolve, 300)),
            ]);
        }

        this._disposeAudioContext();

        const activeUploads = SessionRecorder.uploadsByRecorder.get(this);
        if (activeUploads && activeUploads.size > 0) {
            await Promise.all(activeUploads);
        }
        SessionRecorder.uploadsByRecorder.delete(this);
    }

    _disposeAudioContext() {
        if (!this._audioContext) {
            return;
        }
        if (this._audioContext.state !== "closed") {
            this._audioContext.close();
        }
        this._audioContext = null;
    }
}
