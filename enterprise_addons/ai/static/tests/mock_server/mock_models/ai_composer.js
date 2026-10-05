import { fields, models } from "@web/../tests/web_test_helpers";

export const INTERFACE_KEYS = [
    ["html_field_record", "Write in an HTML field"],
    ["mail_composer", "Write an email"],
    ["html_field_text_select", "Rewrite content"],
    ["chatter_ai_button", "Get help on a record"],
    ["html_prompt_shortcut", "Convert a prompt in an email"],
    ["systray_ai_button", "Ask AI for help"],
    ["voice_transcription_component", "Summary Buttons for Voice Transcription Component"],
    ["file_viewer_ai_button", "Get help on a file attachment"],
    ["media_dialog", "Generate images inside the media manager"],
    ["test_interface_key", "Test Interface Key"],
];

export class AIComposer extends models.ServerModel {
    _name = "ai.composer";

    ai_agent_id = fields.Many2one({ relation: "ai.agent" });
    interface_key = fields.Selection({ selection: INTERFACE_KEYS });

    _store_composer_fields(res) {
        res.attr("interface_key");
    }
}
