import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

import { Component, proxy, useProps } from "@odoo/owl";

export class TtsGenerateField extends Component {
    static template = "voip.TtsGenerateField";

    props = useProps(standardFieldProps);

    setup() {
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.state = proxy({
            hasText: Boolean((this.props.record.data.tts_text || "").trim()),
            isGenerating: false,
        });
        useBus(this.props.record.model.bus, "VOIP:TTS-TEXT-INPUT", (event) => {
            if (event.detail.record === this.props.record) {
                this.state.hasText = event.detail.hasText;
            }
        });
    }

    get generateLabel() {
        return this.state.isGenerating ? _t("Generating...") : _t("Generate");
    }

    get canGenerate() {
        return Boolean(
            !this.state.isGenerating && this.state.hasText && this.props.record.data.tts_voice
        );
    }

    async generateAudio(event) {
        const textarea = event.currentTarget
            .closest(".o-voip-SoundForm-tts")
            .querySelector("textarea");
        const text = textarea.value;
        const voice = this.props.record.data.tts_voice;
        this.state.isGenerating = true;
        try {
            const result = await this.orm.call("voip.sound", "generate_tts_audio_preview", [], {
                name: this.props.record.data.name,
                text,
                voice,
            });
            if (textarea.value !== text || this.props.record.data.tts_voice !== voice) {
                this.notification.add(
                    _t(
                        "The text or voice changed while the audio was being generated. Generate it again."
                    ),
                    { type: "warning" }
                );
                return;
            }
            await this.props.record.update({
                data: { filename: result.filename, content: result.content },
                data_filename: result.filename,
                generated_tts_text: result.text,
                generated_tts_voice: result.voice,
                source_type: "tts",
                tts_text: result.text,
            });
            this.props.record.model.bus.trigger("VOIP:TTS-AUDIO-PREVIEW", {
                content: result.content,
                record: this.props.record,
            });
            this.notification.add(_t("Audio file generated successfully."), { type: "success" });
        } finally {
            this.state.isGenerating = false;
        }
    }
}

registry.category("fields").add("voip_tts_generate", {
    component: TtsGenerateField,
    supportedTypes: ["text"],
});
