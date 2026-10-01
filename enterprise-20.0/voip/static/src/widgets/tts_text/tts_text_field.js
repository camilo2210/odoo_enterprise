import { registry } from "@web/core/registry";
import { TextField, textField } from "@web/views/fields/text/text_field";

export class TtsTextField extends TextField {
    static template = "voip.TtsTextField";

    onTtsInput(event) {
        this.props.record.model.bus.trigger("VOIP:TTS-TEXT-INPUT", {
            hasText: Boolean(event.target.value.trim()),
            record: this.props.record,
        });
    }
}

registry.category("fields").add("voip_tts_text", {
    ...textField,
    component: TtsTextField,
});
