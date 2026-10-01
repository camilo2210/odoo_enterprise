import { onWillDestroy, proxy, t, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { checkFileSize } from "@web/core/utils/files";
import { useBus } from "@web/core/utils/hooks";
import { getDataURLFromFile } from "@web/core/utils/urls";
import { BinaryField, binaryField, binaryFieldProps } from "@web/views/fields/binary/binary_field";
import { FileUploader } from "@web/views/fields/file_handler";

const TELEPHONY_SAMPLE_RATE = 8000;

function writeAscii(dataView, offset, value) {
    for (let index = 0; index < value.length; index++) {
        dataView.setUint8(offset + index, value.charCodeAt(index));
    }
}

/** Convert browser-recorded audio to 8 kHz, 16-bit mono PCM WAV. */
async function convertToTelephonyWav(blob) {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) {
        throw new Error("Web Audio is not supported.");
    }
    const audioContext = new AudioContextClass();
    let audioBuffer;
    try {
        audioBuffer = await audioContext.decodeAudioData(await blob.arrayBuffer());
    } finally {
        await audioContext.close();
    }
    if (!audioBuffer.length || !audioBuffer.numberOfChannels) {
        throw new Error("The recorded audio is empty.");
    }

    const targetLength = Math.max(
        1,
        Math.round((audioBuffer.length * TELEPHONY_SAMPLE_RATE) / audioBuffer.sampleRate)
    );
    const sourceChannels = Array.from({ length: audioBuffer.numberOfChannels }, (_, channel) =>
        audioBuffer.getChannelData(channel)
    );
    const samples = new Int16Array(targetLength);
    const sourceToTargetRatio = audioBuffer.sampleRate / TELEPHONY_SAMPLE_RATE;
    for (let index = 0; index < targetLength; index++) {
        const sourcePosition = Math.min(index * sourceToTargetRatio, audioBuffer.length - 1);
        const leftIndex = Math.floor(sourcePosition);
        const rightIndex = Math.min(leftIndex + 1, audioBuffer.length - 1);
        const fraction = sourcePosition - leftIndex;
        const sample =
            sourceChannels.reduce(
                (sum, channel) =>
                    sum + channel[leftIndex] * (1 - fraction) + channel[rightIndex] * fraction,
                0
            ) / sourceChannels.length;
        const clampedSample = Math.max(-1, Math.min(1, sample));
        samples[index] = Math.round(clampedSample * (clampedSample < 0 ? 32768 : 32767));
    }

    const wavBuffer = new ArrayBuffer(44 + samples.byteLength);
    const dataView = new DataView(wavBuffer);
    writeAscii(dataView, 0, "RIFF");
    dataView.setUint32(4, 36 + samples.byteLength, true);
    writeAscii(dataView, 8, "WAVE");
    writeAscii(dataView, 12, "fmt ");
    dataView.setUint32(16, 16, true);
    dataView.setUint16(20, 1, true);
    dataView.setUint16(22, 1, true);
    dataView.setUint32(24, TELEPHONY_SAMPLE_RATE, true);
    dataView.setUint32(28, TELEPHONY_SAMPLE_RATE * 2, true);
    dataView.setUint16(32, 2, true);
    dataView.setUint16(34, 16, true);
    writeAscii(dataView, 36, "data");
    dataView.setUint32(40, samples.byteLength, true);
    for (let index = 0; index < samples.length; index++) {
        dataView.setInt16(44 + index * 2, samples[index], true);
    }
    return new Blob([wavBuffer], { type: "audio/wav" });
}

export class VoipAudioBinaryField extends BinaryField {
    static template = "voip.AudioBinaryField";
    static components = { ...BinaryField.components, FileUploader };
    props = useProps({
        ...binaryFieldProps,
        audioRecordField: t.string().optional(),
    });

    setup() {
        super.setup();
        this.state = proxy({
            isDragging: false,
            isPlaying: false,
            isRecording: false,
            previewSrc: false,
            recordingError: false,
        });
        this.audio = null;
        this.mediaRecorder = null;
        this.recordingStream = null;
        this.recordingChunks = [];
        useBus(this.props.record.model.bus, "VOIP:TTS-AUDIO-PREVIEW", (event) => {
            if (event.detail.record === this.props.record) {
                this.setPreview(event.detail.content);
            }
        });
        onWillDestroy(() => {
            this.audio?.pause();
            this._stopRecordingStream();
        });
    }

    get canPlay() {
        return Boolean(this.audioSrc);
    }

    get recordLabel() {
        return this.state.isRecording ? _t("Stop") : _t("Record");
    }

    get recordTitle() {
        return this.state.isRecording ? _t("Stop recording") : _t("Record");
    }

    get audioSrc() {
        if (this.state.previewSrc) {
            return this.state.previewSrc;
        }
        const value = this.props.record.data[this.props.name];
        if (!value) {
            return false;
        }
        if (value.content) {
            return `data:audio/*;base64,${value.content}`;
        }
        if (this.props.record.resId && !this.props.record.dirty) {
            const audioRecordId = this.props.audioRecordField
                ? this.props.record.data[this.props.audioRecordField]?.id
                : this.props.record.resId;
            if (!audioRecordId) {
                return false;
            }
            return `/voip/audio/message/${audioRecordId}?v=${
                this.props.record.data.data_version || 0
            }`;
        }
        return false;
    }

    async update({ data, name }) {
        this.setPreview(data);
        await this.props.record.update({
            [this.props.name]: data ? { filename: name, content: data } : false,
            [this.props.fileNameField]: name || "",
            source_type: "upload",
            tts_text: false,
        });
    }

    setPreview(content) {
        this.state.previewSrc = content ? `data:audio/wav;base64,${content}` : false;
    }

    onDragEnter(event) {
        if (event.dataTransfer?.types.includes("Files")) {
            this.state.isDragging = true;
        }
    }

    onDragLeave(event) {
        if (!event.currentTarget.contains(event.relatedTarget)) {
            this.state.isDragging = false;
        }
    }

    async onDrop(event) {
        this.state.isDragging = false;
        const [file] = event.dataTransfer?.files || [];
        if (!file || !checkFileSize(file.size, this.notification)) {
            return;
        }
        if (!file.name.toLowerCase().endsWith(".wav")) {
            this.notification.add(_t("Upload a WAV file."), { type: "danger" });
            return;
        }
        const dataUrl = await getDataURLFromFile(file);
        await this.update({ data: dataUrl.split(",")[1], name: file.name });
    }

    async togglePlay() {
        if (!this.audioSrc) {
            return;
        }
        if (this.state.isPlaying) {
            this.audio.pause();
            this.audio.currentTime = 0;
            return;
        }
        this.audio?.pause();
        this.audio = new Audio(this.audioSrc);
        this.audio.addEventListener("ended", () => (this.state.isPlaying = false));
        this.audio.addEventListener("pause", () => (this.state.isPlaying = false));
        try {
            await this.audio.play();
            this.state.isPlaying = true;
        } catch {
            this.state.isPlaying = false;
        }
    }

    async toggleRecording() {
        if (this.state.isRecording) {
            this.mediaRecorder.stop();
            return;
        }
        if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
            this.state.recordingError = _t("Audio recording is not supported in this browser.");
            return;
        }
        try {
            this.recordingStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.recordingChunks = [];
            this.mediaRecorder = new MediaRecorder(this.recordingStream);
            this.mediaRecorder.addEventListener("dataavailable", (event) => {
                if (event.data.size) {
                    this.recordingChunks.push(event.data);
                }
            });
            this.mediaRecorder.addEventListener("stop", () => this._saveRecording());
            this.mediaRecorder.start();
            this.state.recordingError = false;
            this.state.isRecording = true;
        } catch (error) {
            this.state.recordingError = error.message || _t("Microphone access was denied.");
            this._stopRecordingStream();
        }
    }

    async _saveRecording() {
        const mimeType = this.mediaRecorder.mimeType || "audio/webm";
        const recordedBlob = new Blob(this.recordingChunks, { type: mimeType });
        this._stopRecordingStream();
        if (!recordedBlob.size) {
            this.state.recordingError = _t("No audio was captured.");
            return;
        }
        let wavBlob;
        try {
            wavBlob = await convertToTelephonyWav(recordedBlob);
        } catch {
            this.state.recordingError = _t("The recording could not be converted to WAV.");
            return;
        }
        const fileName = `${this._recordingName()}.wav`;
        const dataUrl = await getDataURLFromFile(
            new File([wavBlob], fileName, { type: wavBlob.type })
        );
        await this.update({ data: dataUrl.split(",")[1], name: fileName });
    }

    _recordingName() {
        return (this.props.record.data.name || "recording")
            .normalize("NFKD")
            .replace(/[\u0300-\u036f]/g, "")
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "-")
            .replace(/^-+|-+$/g, "");
    }

    _stopRecordingStream() {
        this.recordingStream?.getTracks().forEach((track) => track.stop());
        this.recordingStream = null;
        this.mediaRecorder = null;
        this.recordingChunks = [];
        this.state.isRecording = false;
    }
}

registry.category("fields").add("voip_audio_binary", {
    ...binaryField,
    component: VoipAudioBinaryField,
    displayName: _t("Audio File"),
    supportedOptions: [
        ...binaryField.supportedOptions,
        {
            label: _t("Audio record field"),
            name: "audio_record_field",
            type: "field",
        },
    ],
    extractProps: ({ attrs, options }) => ({
        ...binaryField.extractProps({ attrs, options }),
        audioRecordField: options.audio_record_field,
    }),
});
