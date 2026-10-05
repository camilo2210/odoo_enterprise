import {
    getEditableDescendants,
    useEditableDescendants,
} from "@html_editor/others/embedded_component_utils";
import { browser } from "@web/core/browser/browser";
import { rpc, RPCError } from "@web/core/network/rpc";
import {
    Component,
    markup,
    onMounted,
    onWillDestroy,
    onWillStart,
    onWillUnmount,
    proxy,
    t, useListener,
    useProps,
} from "@odoo/owl";
import { user } from "@web/core/user";
import { useBus, useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { AudioVisualizer } from "@ai/components/audio_visualizer/audio_visualizer";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import AudioProcessor, { ProcessorState } from "@ai/core/audio/audio_processor";
import RealtimeClient from "@ai/core/realtime_client";
import { AITranscriptionEvent, transcriptionBus } from "@ai/core/transcription_bus";

export class VoiceTranscription extends Component {
    static components = { AudioVisualizer, Dropdown, DropdownItem };
    static template = "ai.VoiceTranscription";

    props = useProps({
        onTranscriptionStarted: t.function(),
        onTranscriptionUpdated: t.function(),
        onSummaryUpdated: t.function(),
    });

    setup() {
        super.setup();
        const { descendants, refs } = useEditableDescendants();
        this.descendants = descendants;
        this.descendantRefs = refs;
        this.actionService = useService("action");
        this.notificationService = useService("notification");
        this.ui = useService("ui");
        this.orm = useService("orm");
        this.mailStore = useService("mail.store");

        this.shouldCommit = false;
        this.supportedLanguages = [];

        this.iapTransactionToken = null;
        this.usage = {};

        const currentLanguage = user.lang.replace("-", "_");
        const hasSummary = this.descendants.summaryContent.textContent.trim() !== "";
        this.state = proxy({
            frequencies: new Uint8Array(),
            currentTab: "notes",
            currentLanguage: {
                code: currentLanguage,
                shortCode: currentLanguage.split("_")[0],
            },
            hasSummary,
            isOpened: true,
            isRecording: false,
            status: "idle",
        });

        this.summaryObserver = new MutationObserver((mutationList) => {
            for (const mutation of mutationList) {
                if (mutation.type === "childList" || mutation.type === "characterData") {
                    this.state.hasSummary =
                        this.descendants.summaryContent.textContent.trim() !== "";
                }
            }
        });
        this.summaryObserver.observe(this.descendants.summaryContent, {
            childList: true,
            characterData: true,
        });

        this.realtimeClient = RealtimeClient.getInstance();

        // To take care of the case where the user closes the tab while the transcription is active
        useListener(browser, "pagehide", () => this.resetIAPTracking());

        // Subscribe to event for the RealtimeClient
        useBus(transcriptionBus, AITranscriptionEvent.REALTIME_CLIENT_MESSAGE, (event) => {
            if (this.state.status !== "recording") {
                return;
            }
            const data = event.detail;
            if (data.type === "conversation.item.input_audio_transcription.completed") {
                this.usage["input_tokens"]["text"] += data.usage.input_token_details?.text_tokens || 0;
                this.usage["input_tokens"]["audio"] += data.usage.input_token_details?.audio_tokens || 0;
                this.usage["output_tokens"] += data.usage.output_tokens || 0;
                this.usage["duration_seconds"] += data.usage.duration || 0;

                this.props.onTranscriptionUpdated(
                    "delta",
                    this.descendants.transcriptContent,
                    data.transcript
                );
                if (this.shouldCommit) {
                    this.props.onTranscriptionUpdated(
                        "completed",
                        this.descendants.transcriptContent
                    );
                    this.shouldCommit = false;
                }
            }
        });

        this.audioProcessor = AudioProcessor.getInstance();

        // Subscribe events for the AudioProcessor
        useBus(transcriptionBus, AITranscriptionEvent.AUDIO_PROCESSOR_DATA, (event) =>
            this.realtimeClient.send(event.detail)
        );
        useBus(
            transcriptionBus,
            AITranscriptionEvent.AUDIO_PROCESSOR_FREQUENCY,
            (event) => (this.state.frequencies = event.detail)
        );
        useBus(transcriptionBus, AITranscriptionEvent.AUDIO_PROCESSOR_STATE, (event) => {
            if (this.state.status !== "recording") {
                return;
            }
            switch (event.detail) {
                case "recording":
                    this.props.onTranscriptionUpdated(
                        "listening",
                        this.descendants.transcriptContent,
                        _t("AI is listening...")
                    );
                    break;
                case "stopped":
                    this.shouldCommit = true;
                    break;
            }
        });

        onWillStart(async () => {
            const languages = await this.orm.call("res.lang", "get_installed", []);
            this.supportedLanguages = languages.map(([code]) => ({
                shortCode: code.split("_")[0],
                code,
            }));

            if (this.audioProcessor.state !== ProcessorState.IDLE) {
                this.state.status = "recording";
            }

            this.transcriptionComposer = await this.orm.call(
                "ai.composer",
                "retrieve_transcription_composer",
                [],
                {
                    record_model: this.env.model?.config.resModel,
                }
            );

            if (this.state.hasSummary) {
                this.state.currentTab = "summary";
            }
        });

        onMounted(() => {
            this.state.firstRecordingDate =
                this.descendants.transcriptContent.querySelector("b")?.innerText;
        });

        onWillUnmount(() => {
            this.resetIAPTracking();
        });

        onWillDestroy(() => {
            this.summaryObserver.disconnect();
        });
    }

    async resetIAPTracking() {
        if (this.iapTransactionToken !== null) {
            try {
                await rpc("/ai/transcription/report_realtime_session_usage", {
                    "iap_transaction_token": this.iapTransactionToken,
                    "usage": this.usage,
                });
            } catch (e) {
                console.error("Failed to report usage to IAP", e);
            }
        }
        this.iapTransactionToken = null;
        this.usage = {
            "input_tokens": {
                "text": 0,
                "audio": 0,
            },
            "output_tokens": 0,
            "duration_seconds": 0,
        };
    }

    setCurrentTab(tabName) {
        this.state["currentTab"] = tabName;
    }

    async toggleRecording() {
        this.state.isRecording = !this.state.isRecording;
        if (this.state.status === "idle") {
            const transcriptPrompt = this.descendants.notesContent;
            try {
                this.state.status = "waiting";
                const response = await rpc("/ai/transcription/session", {
                    language: this.state.currentLanguage.shortCode,
                    prompt: transcriptPrompt?.innerText.trim(),
                });
                if (response["status"] === "success") {
                    const sessionToken = response["session_token"];
                    await this.resetIAPTracking();
                    this.iapTransactionToken = response["iap_transaction_token"];
                    this.realtimeClient.connect(sessionToken);
                    this.state.status = "recording";
                    this.props.onTranscriptionStarted(
                        this.descendants.transcriptContent,
                        this.state.currentLanguage.code.replace("_", "-")
                    );
                    await this.audioProcessor.start();
                    this.setCurrentTab("transcript");
                }
                else if (response["status"] === "insufficient_credit") {
                    // The notification is already handled by call_odoo_ai
                    this.state.status = "idle";
                    this.state.isRecording = false;
                }
            } catch (error) {
                this.state.status = "idle";
                this.state.isRecording = false;
                if (error instanceof DOMException && error.name === "NotAllowedError") {
                    this.notificationService.add(
                        _t(
                            "You must allow the access to your microphone to start the recording. Try refreshing the page and start again."
                        ),
                        {
                            title: _t("Access error"),
                            type: "danger",
                        }
                    );
                } else if (
                    error instanceof RPCError &&
                    error.data.name === "odoo.exceptions.UserError"
                ) {
                    this.notificationService.add(error.data.message, {
                        type: "danger",
                    });
                } else {
                    this.notificationService.add(_t("Unable to start the recording."), {
                        title: _t("An error occurred"),
                        type: "danger",
                    });
                }
            }
        } else if (this.state.status === "recording") {
            await this.resetIAPTracking();
            this.audioProcessor.stop();
            this.realtimeClient.disconnect();
            this.props.onTranscriptionUpdated("stopped", this.descendants.transcriptContent);
            this.updateSummary();
        }
    }

    async updateSummary(promptButton = null) {
        this.state.status = "summarizing";
        const summary = await this.getSummary(promptButton);
        if (summary) {
            this.props.onSummaryUpdated(this.descendants.summaryContent, summary);
            this.setCurrentTab("summary");
        }
        this.state.status = "idle";
    }

    async getSummary(promptButton = null) {
        const textToSummarize = this.getTranscriptContent();
        if (!this.transcriptionComposer || textToSummarize?.trim() === "") {
            return null;
        }

        const message = await rpc("/ai/transcription/summary", {
            composer_id: this.transcriptionComposer.id,
            summarization_instructions: `You MUST provide the summary in the following language: ${this.state.currentLanguage.code}`,
            text_to_summarize: textToSummarize,
            ai_prompt_button_context: {
                ai_prompt_button_ref: promptButton?.id,
                rendering_record_id: this.env.model?.config.resId,
            },
        });
        return markup(message);
    }

    getTranscriptContent() {
        const transcriptElements =
            this.descendants.transcriptContent.querySelectorAll("blockquote");
        const transcript = [];
        transcriptElements.forEach((element) => {
            const innerText = element.innerText.trim();
            if (innerText !== "") {
                transcript.push(innerText);
            }
        });
        return transcript.join("\n");
    }

    async openComposer() {
        const model = this.env.model;
        await model?.root.save();
        this.actionService.doAction(
            {
                type: "ir.actions.act_window",
                name: _t("Share transcript summary"),
                view_mode: "form",
                res_model: "mail.compose.message",
                views: [[false, "form"]],
                target: "new",
                view_id: false,
                context: {
                    default_model: model?.config.resModel,
                    default_res_ids: [model?.config.resId],
                    default_subject: _t("Share transcript summary"),
                    default_body: this.descendants.summaryContent.innerHTML,
                    is_full_composer: true,
                },
            },
            {
                onClose: async () => {
                    const thread = this.mailStore["mail.thread"].get({
                        model: model?.config.resModel,
                        id: model?.config.resId,
                    });
                    await thread?.fetchNewMessages();
                },
            }
        );
    }
    get sortedPromptButtons() {
        return (this.transcriptionComposer.available_prompt_ids || []).sort(
            (a, b) => a.sequence - b.sequence
        );
    }
}

export const aiVoiceTranscriptionEmbeddedComponent = {
    name: "voice-transcription",
    Component: VoiceTranscription,
    getEditableDescendants: getEditableDescendants,
    getProps: (host) => ({ host }),
};
