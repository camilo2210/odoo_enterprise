import { patch } from "@web/core/utils/patch";
import {
    registerComposerAction,
    ComposerAction,
    describeComposerActionGroup,
} from "@mail/core/common/composer_actions";
import { VoiceRecorder } from "@mail/discuss/voice_message/common/voice_recorder";
import { Component } from "@odoo/owl";
import { AiSessionToggle } from "@ai/components/ai_composer_actions_selectors/ai_session_toggle";
import { _t } from "@web/core/l10n/translation";

patch(ComposerAction.prototype, {
    _getAiComposerActions() {
        return [
            "send-message",
            "upload-files",
            "voice-start",
            "voice-recording",
            "voice-transcribing",
            "toggle-think-longer",
            "toggle-restrict-to-resources",
            "toggle-web-search",
            "toggle-action-auto-approve",
            "toggle-agent-steps",
        ];
    },
    _condition({ composer, owner }) {
        if (composer.targetThread?.channel?.isAiChat) {
            const hasText = !!composer.composerText;
            const hasAttachments = composer.attachments && composer.attachments.length > 0;

            // Replace "empty" Send button with Dictate
            if (this.id === "send-message" && !hasText && !hasAttachments) {
                return false;
            }
            // Replace Dictate with Send or Recorder
            if (this.id === "voice-start" && hasText) {
                return false;
            }
            if (this.id === "voice-start" && owner?.voiceTranscription?.isTranscribing) {
                return false;
            }
        }

        if (
            composer.targetThread?.channel?.isAiChat &&
            !this._getAiComposerActions().includes(this.id)
        ) {
            return false;
        }
        return super._condition(...arguments);
    },
    _name({ composer }) {
        if (composer.targetThread?.channel?.isAiChat) {
            if (this.id === "send-message") {
                return _t("Send (%(keyboard_command)s)", { keyboard_command: "Enter" });
            }
            if (this.id === "voice-start") {
                return _t("Voice Message (%(keyboard_command)s)", { keyboard_command: "Alt+V" });
            }
        }
        return super._name(...arguments);
    },
    _sequence({ composer }) {
        if (composer.targetThread?.channel?.isAiChat && this.id === "voice-start") {
            // Remove the microphone from the bottom "Extra Actions" toolbar
            return undefined;
        }
        return super._sequence(...arguments);
    },
    _sequenceQuick({ composer }) {
        if (composer.targetThread?.channel?.isAiChat && this.id === "voice-start") {
            // Place microphone next to text input
            return 25;
        }
        return super._sequenceQuick(...arguments);
    },
});
patch(VoiceRecorder.prototype, {
    get title() {
        if (this.props.composer.targetThread?.channel?.isAiChat) {
            return _t("Convert to text (%(keyboard_command_1)s) or Send (%(keyboard_command_2)s)", {
                keyboard_command_1: "Alt+V",
                keyboard_command_2: "Enter",
            });
        }
        return super.title;
    },
    get cancelTitle() {
        if (this.props.composer.targetThread?.channel?.isAiChat) {
            return _t("Cancel (%(keyboard_command)s)", { keyboard_command: "Esc" });
        }
        return super.cancelTitle;
    },
});

describeComposerActionGroup(20, { name: _t("AI Chat Settings") });

registerComposerAction("voice-transcribing", {
    component: class VoiceMessageTranscribingSpinner extends Component {
        static template = "ai.VoiceMessageTranscribingSpinner";
    },
    condition: ({ composer, owner }) =>
        composer.targetThread?.channel?.isAiChat && owner?.voiceTranscription?.isTranscribing,
    sequenceQuick: 11,
});

registerComposerAction("toggle-action-auto-approve", {
    condition: ({ composer }) => composer.targetThread?.channel?.isAiChat,
    closingModeAsDropdown: "none",
    extraContentComponent: AiSessionToggle,
    extraContentComponentProps: ({ composer }) => ({
        aiSession: composer.targetThread.channel.aiSession,
        configAttribute: "auto_confirm",
    }),
    icon: "verified",
    name: _t("Auto-Approve Actions"),
    onSelected({ composer }) {
        const aiSession = composer.targetThread.channel.aiSession;
        aiSession.updateConfig("auto_confirm", !aiSession.config["auto_confirm"]);
    },
    sequence: 20,
    sequenceGroup: 20,
});

registerComposerAction("toggle-web-search", {
    condition: ({ composer }) => composer.targetThread?.channel?.isAiChat,
    closingModeAsDropdown: "none",
    extraContentComponent: AiSessionToggle,
    extraContentComponentProps: ({ composer }) => ({
        aiSession: composer.targetThread.channel.aiSession,
        configAttribute: "enable_web_search",
    }),
    icon: "search",
    name: _t("Web Search"),
    onSelected({ composer }) {
        const aiSession = composer.targetThread.channel.aiSession;
        aiSession.updateConfig("enable_web_search", !aiSession.config["enable_web_search"]);
    },
    sequence: 21,
    sequenceGroup: 20,
});

registerComposerAction("toggle-restrict-to-resources", {
    condition: ({ composer }) =>
        composer.targetThread?.channel?.isAiChat &&
        (composer.targetThread?.channel?.ai_agent_id?.sources_ids?.length ?? 0) > 0,
    closingModeAsDropdown: "none",
    extraContentComponent: AiSessionToggle,
    extraContentComponentProps: ({ composer }) => ({
        aiSession: composer.targetThread.channel.aiSession,
        configAttribute: "enable_resources_only",
    }),
    icon: "book",
    name: _t("Restrict to Sources"),
    onSelected({ composer }) {
        const aiSession = composer.targetThread.channel.aiSession;
        aiSession.updateConfig("enable_resources_only", !aiSession.config["enable_resources_only"]);
    },
    sequence: 22,
    sequenceGroup: 20,
});

registerComposerAction("toggle-agent-steps", {
    condition: ({ composer }) => composer.targetThread?.channel?.isAiChat,
    closingModeAsDropdown: "none",
    extraContentComponent: AiSessionToggle,
    extraContentComponentProps: ({ composer }) => ({
        aiSession: composer.targetThread.channel.aiSession,
        configAttribute: "show_agent_steps",
    }),
    icon: "checklist",
    name: _t("Show Steps"),
    onSelected({ composer }) {
        const aiSession = composer.targetThread.channel.aiSession;
        aiSession.updateConfig("show_agent_steps", !aiSession.config["show_agent_steps"]);
    },
    sequence: 23,
    sequenceGroup: 20,
});

registerComposerAction("toggle-think-longer", {
    condition: ({ composer }) => composer.targetThread?.channel?.isAiChat,
    closingModeAsDropdown: "none",
    extraContentComponent: AiSessionToggle,
    extraContentComponentProps: ({ composer }) => ({
        aiSession: composer.targetThread.channel.aiSession,
        configAttribute: "enable_think_longer",
    }),
    icon: "lightbulb",
    name: _t("Think Longer"),
    onSelected({ composer }) {
        const aiSession = composer.targetThread.channel.aiSession;
        aiSession.updateConfig("enable_think_longer", !aiSession.config["enable_think_longer"]);
    },
    sequence: 24,
    sequenceGroup: 20,
});
