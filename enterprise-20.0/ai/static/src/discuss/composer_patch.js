import { Composer } from "@mail/core/common/composer";
import "@ai/discuss/core/common/composer_patch";
//Ensure base voice_message patch is applied before this one
import "@mail/discuss/voice_message/common/composer_patch";
import { useVoiceRecorder } from "@mail/discuss/voice_message/common/voice_recorder";
import { proxy } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { getDataURLFromFile } from "@web/core/utils/urls";

patch(Composer.prototype, {
    setup() {
        super.setup();
        const notificationService = this.env.services.notification;
        this.voiceTranscription = proxy({ isTranscribing: false });
        this.uiService = useService("ui");

        if (this.props.composer.targetThread?.channel?.isAiChat) {
            const transcribe = async (file) => {
                this.voiceTranscription.isTranscribing = true;
                try {
                    const dataUrl = await getDataURLFromFile(file);
                    const base64Audio = dataUrl.split(",")[1];
                    const response = await rpc(
                        "/ai/transcription",
                        {
                            audio_base64: base64Audio,
                            language: user.lang?.replace("-", "_").split("_")[0],
                        },
                        { silent: true },
                    );
                    if (response["status"] === "success") {
                        const text = response["text"];
                        // Append rather than overwrite protects existing text
                        const prefix = this.props.composer.composerText ? " " : "";
                        this.props.composer.insertText(
                            prefix + text,
                            this.props.composer.selection.start,
                            { moveCursorToEnd: true },
                        );
                    }
                } catch {
                    notificationService.add(_t("Transcription failed."), {
                        type: "danger",
                    });
                } finally {
                    this.voiceTranscription.isTranscribing = false;
                }
            };

            // Transcribe voice uploads instead of sending them as attachments
            this.voiceRecorder = useVoiceRecorder({
                maxDuration: 1200, // Stay well within 25MB limit (at 128kbps)
                onRecordReady: transcribe,
            });

            // Restore focus after starting recording (so keybindings work)
            const originalOnClick = this.voiceRecorder.onClick;
            this.voiceRecorder.onClick = async (...args) => {
                const res = await originalOnClick.apply(this.voiceRecorder, args);
                if (this.voiceRecorder.recording) {
                    if (this.composerService.htmlEnabled) {
                        this.editor?.shared.selection.focusEditable();
                    } else {
                        this.ref()?.focus();
                    }
                }
                return res;
            };
        }
    },
    saveContent() {
        if (this.props.composer.targetThread?.channel?.isAiChat) {
            return; // no point in saving the content in an AI chat since chats are independent
        }
        super.saveContent();
    },
    onFocusin(ev) {
        const isBusy = this.voiceRecorder?.recording || this.voiceTranscription?.isTranscribing;
        // On mobile, prevent the virtual keyboard from popping up
        if (
            this.props.composer.targetThread?.channel?.isAiChat &&
            isBusy &&
            this.uiService.isSmall
        ) {
            ev.target.blur();
            return;
        }
        super.onFocusin(ev);
        if (this.props.composer.targetThread?.channel?.isAiChat) {
            if (this.composerService.htmlEnabled) {
                this.editor?.shared.selection.focusEditable();
            } else {
                ev.target.select();
            }
        }
    },
    get isSendButtonDisabled() {
        if (this.props.composer.targetThread?.channel?.isAiChat && this.voiceRecorder?.recording) {
            return this.isAiAgentGenerating;
        }
        return super.isSendButtonDisabled;
    },
    get SEND_TEXT() {
        if (this.props.composer.targetThread?.channel?.isAiChat) {
            return _t("%(send_text)s (Enter)", {
                send_text: super.SEND_TEXT,
            });
        }
        return super.SEND_TEXT;
    },
    async sendMessage() {
        if (
            !this.isAiAgentGenerating &&
            this.props.composer.targetThread?.channel?.isAiChat &&
            this.voiceRecorder?.recording
        ) {
            await this.voiceRecorder.onClick();
        }
        return super.sendMessage();
    },
    onKeydown(ev) {
        if (this.props.composer.targetThread?.channel?.isAiChat) {
            const isRecording = this.voiceRecorder?.recording;
            const isTranscribing = this.voiceTranscription?.isTranscribing;
            const isBusy = isRecording || isTranscribing;

            if (ev.key === "Enter") {
                if (!ev.shiftKey && isRecording) {
                    ev.preventDefault();
                    ev.stopPropagation();
                    this.voiceRecorder.onClick().then(() => this.sendMessage());
                    return;
                }
            }
            if (ev.key === "Escape" && isRecording) {
                ev.preventDefault();
                ev.stopPropagation();
                this.voiceRecorder.cancelRecording();
                return;
            }
            if (ev.altKey && ev.key.toLowerCase() === "v") {
                ev.preventDefault();
                ev.stopPropagation();
                this.voiceRecorder?.onClick();
                return;
            }

            // We manually block character input during recording/transcribing
            // instead of HTML disabled attr, which would restrict focus;
            // keeping focus allows to scope shourtcut capture
            if (
                isBusy &&
                !ev.ctrlKey &&
                !ev.altKey &&
                !ev.metaKey &&
                ev.key !== "Tab" &&
                ev.key !== "Enter"
            ) {
                ev.preventDefault();
                ev.stopPropagation();
                return;
            }
        }
        return super.onKeydown(ev);
    },
    get placeholder() {
        if (this.props.composer.targetThread?.channel?.isAiChat && this.voiceRecorder?.recording) {
            return _t("Listening…");
        }
        return super.placeholder;
    },
    get supportedFileTypes() {
        if (!this.props.composer.targetThread?.channel?.isAiChat) {
            return undefined;
        }
        // indexable files and image types supported by most AI providers
        return "text/*,application/pdf,.docx,.pptx,.xlsx,.opendoc,.png,.jpg,.jpeg,.webp,.gif";
    },
    get wysiwygConfig() {
        const config = super.wysiwygConfig;
        return {
            ...config,
            getRecordInfo: () => ({
                resModel: this.thread?.model,
                resId: this.thread?.id,
            }),
        };
    },
});
