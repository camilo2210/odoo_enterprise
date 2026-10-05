import { url } from "@web/core/utils/urls";
import { AITranscriptionEvent, transcriptionBus } from "@ai/core/transcription_bus";

const VADState = {
    SILENCE: "silence",
    SPEECH: "speech",
};

export const ProcessorState = {
    IDLE: "idle",
    RECORDING: "recording",
    PAUSED: "paused",
    STOPPED: "stopped",
};

export default class AudioProcessor {
    /** @type{AudioProcessor} */
    static instance = null;

    /**
     * @param {function(string): void} onStateChange function called when the state is updated
     */
    constructor(
        analyserOptions = {
            fftSize: 128,
        }
    ) {
        this.analyserOptions = analyserOptions;

        if (this.audioContext?.state === "running") {
            this._state = "recording";
        } else {
            this._state = "idle";
        }

        this.animationFrame = null;
        this.silenceTimer = null;

        /** @type {AudioContext} */
        this.audioContext = null;
        /** @type {MediaStream} */
        this.audioStream = null;
        /** @type {AnalyserNode} */
        this.analyserNode = null;
    }

    /**
     * Retrieves the singleton instance of the AudioProcessor.
     *
     * @param {function(string): void} onStateChange function called when the state is updated
     */
    static getInstance(
        analyserOptions = {
            fftSize: 128,
        }
    ) {
        if (AudioProcessor.instance === null) {
            AudioProcessor.instance = new AudioProcessor(analyserOptions);
        }
        return AudioProcessor.instance;
    }

    get state() {
        return this._state;
    }

    set state(newState) {
        if (this._state !== newState) {
            this._state = newState;
            transcriptionBus.trigger(AITranscriptionEvent.AUDIO_PROCESSOR_STATE, newState);
        }
    }

    async start() {
        if (this.audioStream === null) {
            this.audioStream = await navigator.mediaDevices.getUserMedia({
                audio: true,
            });
        }
        if (!this.audioContext || this.audioContext.state === "closed") {
            this.audioContext = new AudioContext();
            const audioContext = this.audioContext;

            const sourceNode = audioContext.createMediaStreamSource(this.audioStream);
            this.analyserNode = audioContext.createAnalyser();

            const workletUrl = url("/ai/static/src/core/audio/pcm16_audio_worklet.js");
            await audioContext.audioWorklet.addModule(workletUrl);
            const pcm16AudioProcessorNode = new AudioWorkletNode(audioContext, "pcm16-processor");

            if (audioContext.state === "suspended") {
                await audioContext.resume();
            }
            sourceNode.connect(this.analyserNode);
            this.analyserNode.connect(pcm16AudioProcessorNode);
            pcm16AudioProcessorNode.connect(audioContext.destination);

            pcm16AudioProcessorNode.port.onmessage = (event) => {
                const payload = event.data;
                if (payload.type === "audio") {
                    transcriptionBus.trigger(
                        AITranscriptionEvent.AUDIO_PROCESSOR_DATA,
                        new Uint8Array(payload.data)
                    );
                } else if (payload.type === "vad") {
                    if (payload.state === VADState.SILENCE) {
                        if (this.state === ProcessorState.RECORDING) {
                            this.state = ProcessorState.PAUSED;
                            this.silenceTimer = setTimeout(() => {
                                if (this.state === ProcessorState.PAUSED) {
                                    this.state = ProcessorState.STOPPED;
                                }
                            }, 1000);
                        }
                    } else {
                        if (this.state !== ProcessorState.RECORDING) {
                            clearTimeout(this.silenceTimer);
                            this.silenceTimer = null;
                        }
                        this.state = ProcessorState.RECORDING;
                    }
                }
            };
        }
        this.state = ProcessorState.RECORDING;
        this.runFrequencyAnalysis();
    }

    runFrequencyAnalysis() {
        const analyseFrequencies = () => {
            const data = new Uint8Array(this.analyserNode.frequencyBinCount);
            this.analyserNode.getByteFrequencyData(data);
            transcriptionBus.trigger(AITranscriptionEvent.AUDIO_PROCESSOR_FREQUENCY, data);
            this.animationFrame = requestAnimationFrame(analyseFrequencies);
        };
        this.animationFrame = requestAnimationFrame(analyseFrequencies);
    }

    stop() {
        if (this.animationFrame) {
            cancelAnimationFrame(this.animationFrame);
            this.animationFrame = null;
        }

        if (this.silenceTimer) {
            clearTimeout(this.silenceTimer);
            this.silenceTimer = null;
        }

        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }

        if (this.audioStream) {
            this.audioStream.getTracks().forEach((track) => track.stop());
            this.audioStream = null;
        }

        this.state = ProcessorState.IDLE;
    }
}
