import { Component, onWillDestroy, proxy, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

let activeAudio;

export class VoipAudioListPlayField extends Component {
    static template = "voip.AudioListPlayField";

    props = useProps(standardFieldProps);

    setup() {
        this.state = proxy({ isPlaying: false });
        this.audio = null;
        onWillDestroy(() => this.audio?.pause());
    }

    get canPlay() {
        return Boolean(this.props.record.resId && this.props.record.data[this.props.name]);
    }

    get audioSrc() {
        if (this.props.record.resModel === "voip.voicemail.message") {
            return `/voip/voicemail/message/${this.props.record.resId}?v=${
                this.props.record.data.recording_version || 0
            }`;
        }
        return `/voip/audio/message/${this.props.record.resId}?v=${
            this.props.record.data.data_version || 0
        }`;
    }

    async togglePlay() {
        if (!this.canPlay) {
            return;
        }
        if (this.state.isPlaying) {
            this.audio.pause();
            this.audio.currentTime = 0;
            return;
        }
        activeAudio?.pause();
        this.audio = new Audio(this.audioSrc);
        this.audio.addEventListener("ended", () => (this.state.isPlaying = false));
        this.audio.addEventListener("pause", () => (this.state.isPlaying = false));
        try {
            await this.audio.play();
            activeAudio = this.audio;
            this.state.isPlaying = true;
        } catch {
            this.state.isPlaying = false;
        }
    }
}

registry.category("fields").add("voip_audio_list_play", {
    component: VoipAudioListPlayField,
    displayName: _t("Audio Play"),
    supportedTypes: ["binary"],
});
