import { onWillStart, proxy } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { SelectionField, selectionField } from "@web/views/fields/selection/selection_field";

/**
 * Voice `SelectionField` with a "Language" filter fetched once and applied
 * client-side: Telnyx offers no server-side language filter, and the
 * catalog is cached server-side anyway, so re-fetching on every language
 * change would only add latency for the same payload.
 */
export class TTSVoiceSelectionField extends SelectionField {
    static template = "voip.TTSVoiceSelectionField";

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.state = proxy({ voices: null, languages: [], languageFilter: null });
        onWillStart(async () => {
            let data;
            try {
                data = await this.orm.call("voip.sound", "get_tts_voices_by_language", []);
            } catch {
                return;
            }
            this.state.voices = data.voices;
            this.state.languages = data.languages;
            // An existing record keeps the language of its already-saved
            // voice (e.g. after the "Generate" button's reload) instead of
            // snapping to the logged-in user's language, which could hide
            // that voice from the filtered list entirely.
            const currentVoice =
                this.props.record.resId &&
                this.state.voices.find((voice) => voice.voice_id === this.value);
            this.state.languageFilter = currentVoice?.language_code ?? data.default_language_code;
            if (!this.props.record.resId) {
                // New record: replace the field's hardcoded Python default
                // with the first voice of the default language, so Voice
                // always matches what Language actually shows.
                const firstVoiceId = this.options[0]?.[0];
                if (firstVoiceId) {
                    this.onChange(firstVoiceId);
                }
            }
        });
    }

    get languagePlaceholder() {
        return _t("Language");
    }

    get languageChoices() {
        return this.state.languages.map((language) => ({
            value: language.code,
            label: language.name,
        }));
    }

    get options() {
        if (!this.state.voices) {
            // Not loaded yet (or the RPC failed): fall back to the field's
            // own server-computed selection so the widget stays usable.
            return super.options;
        }
        return this.state.voices
            .filter((voice) => voice.language_code === this.state.languageFilter)
            .map((voice) => [voice.voice_id, voice.label]);
    }

    onLanguageChange(languageCode) {
        this.state.languageFilter = languageCode;
        if (!this.options.some((option) => option[0] === this.value)) {
            this.onChange(this.options[0]?.[0] ?? false);
        }
    }
}

export const ttsVoiceSelectionField = {
    ...selectionField,
    component: TTSVoiceSelectionField,
    displayName: _t("Voice (with language filter)"),
};

registry.category("fields").add("voip_tts_voice_selection", ttsVoiceSelectionField);
