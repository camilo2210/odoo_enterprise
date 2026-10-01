import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { animationFrame, queryOne } from "@odoo/hoot-dom";
import { TranscriptionPlugin } from "../src/editor/embedded_components/plugins/voice_transcription_plugin";
import { aiVoiceTranscriptionEmbeddedComponent } from "../src/editor/embedded_components/core/voice_transcription";
import {
    defineModels,
    fields,
    makeMockServer,
    models,
    onRpc,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";
import { renderToString } from "@web/core/utils/render";
import { defineAIModels } from "./ai_test_helpers";
import { contains, click } from "@mail/../tests/mail_test_helpers";
import {
    setupMultiEditor,
    validateSameHistory,
} from "@html_editor/../tests/_helpers/collaboration";
import { commit, tripleClick } from "@html_editor/../tests/_helpers/user_actions";
import { cleanHints } from "@html_editor/../tests/_helpers/dispatch";
import { parseHTML } from "@html_editor/utils/html";
import { setupEditor } from "@html_editor/../tests/_helpers/editor";
import { user } from "@web/core/user";
import { EmbeddedComponentPlugin } from "@html_editor/others/embedded_component_plugin";
import RealtimeClient from "../src/core/realtime_client";
import AudioProcessor from "../src/core/audio/audio_processor";
import { AITranscriptionEvent, transcriptionBus } from "@ai/core/transcription_bus";

class Dummy extends models.Model {
    _name = "dummy";

    name = fields.Char();
    message_ids = fields.One2many({
        relation: "mail.message",
        string: "Messages",
    });

    _records = [
        { id: 1, name: "Bob" },
        { id: 2, name: "Patrick" },
        { id: 3, name: "Sheldon" },
    ];
}

defineModels([Dummy]);
defineAIModels();

beforeEach(() => {
    onRpc("ai.composer", "retrieve_transcription_composer", () => ({}));
    onRpc("/ai/transcription/summary", () => "<p>This is a response</p>");
    onRpc("/ai/transcription/session", () => {
        return {
            'status': 'success',
            'session_token': 'some_session_token',
            'iap_transaction_token': 'some_transaction_token',
        }
    });
    onRpc("/ai/transcription/report_realtime_session_usage", ({ args }) => {
        expect(args.iapTransactionToken).toBe("some_transaction_token");
        expect(args.usage).toEqual({
            "input_tokens": {
                "text": 1,
                "audio": 1,
            },
            "output_tokens": 1,
            "duration_seconds": 1,
        });
    });

    patchWithCleanup(RealtimeClient.prototype, {
        connect(_sessionInfo) {
            if (this.socket === null) {
                this.socket = new WebSocket();
            }

            this.socket.addEventListener("message", (event) => {
                const jsonData = JSON.parse(event.data);
                transcriptionBus.trigger(AITranscriptionEvent.REALTIME_CLIENT_MESSAGE, jsonData);
            });
        },
    });

    patchWithCleanup(AudioProcessor.prototype, {
        async start() {
            this.state = "recording";
        },
        stop() {
            this.state = "idle";
        },
    });

    patchWithCleanup(user, {
        lang: "en-US",
    });
});

function getCurrentDate() {
    const today = new Date();
    const timeString = today.toLocaleTimeString([user.lang], {
        hour: "2-digit",
        minute: "2-digit",
    });
    return `${today.toLocaleDateString()} - ${timeString}`;
}

const testAiVoiceTranscriptionEmbeddedComponent = {
    ...aiVoiceTranscriptionEmbeddedComponent,
    Component: class AudioTranscriber extends aiVoiceTranscriptionEmbeddedComponent.Component {},
};

const config = {
    includePlugins: [EmbeddedComponentPlugin, TranscriptionPlugin],
    resources: {
        embedded_components: [testAiVoiceTranscriptionEmbeddedComponent],
    },
    getRecordInfo: () => ({
        resModel: "dummy",
        resId: "1",
    }),
    collaboration: {
        peerId: 1,
    },
};

function generateTranscriptionEvent() {
    return new MessageEvent("message", {
        data: JSON.stringify({
            item_id: 1,
            type: "conversation.item.input_audio_transcription.completed",
            transcript: "This is a test of transcription",
            usage: {
                "input_token_details": {
                    "text_tokens": 1,
                    "audio_tokens": 1,
                },
                "output_tokens": 1,
                "duration": 1,
            },
        }),
    })
}

describe("Component behaviour", () => {
    test.tags("desktop");
    test("transcript component tabs have proper hints", async () => {
        const transcriptBlock = renderToString("ai.VoiceTranscriptionBlueprint");
        await setupEditor(`<p>[]</p>${transcriptBlock}`, {
            config,
        });

        expect("[data-embedded='voice-transcription']").toHaveCount(1);
        expect("button:contains(Notes)").toHaveClass("active");
        expect("[data-embedded-editable='notesContent'] .o-we-hint").toHaveAttribute(
            "o-we-hint-text",
            "Add notes about your upcoming meeting"
        );
        await click("button:contains(Transcript)");
        await animationFrame();
        expect("button:contains(Transcript)").toHaveClass("active");
        expect("[data-embedded-editable='transcriptContent'] .o-we-hint").toHaveAttribute(
            "o-we-hint-text",
            "Start recording to get a real-time transcript of the conversation"
        );
        await tripleClick(queryOne("[data-embedded-editable='transcriptContent'] .o-we-hint>br"));
        await animationFrame();
        expect("[data-embedded-editable='transcriptContent'] .o-we-hint").toHaveAttribute(
            "o-we-hint-text",
            'Type "/" for commands'
        );
    });

    test.tags("desktop");
    test("transcription items are properly rendered", async () => {
        const transcriptBlock = renderToString("ai.VoiceTranscriptionBlueprint");
        await setupEditor(`<p>[]</p>${transcriptBlock}`, {
            config,
        });

        expect("[data-embedded='voice-transcription']").toHaveCount(1);
        await click("button:contains(Start Recording)");
        await animationFrame();
        expect("button:contains(Transcript)").toHaveClass("active");
        expect("[data-embedded-editable='transcriptContent'] p>b").toHaveText(getCurrentDate());

        expect(`[data-id='current-transcript-${config.collaboration.peerId}']`).toHaveCount(1);
        expect(".o-ai-transcription-listening").toHaveText("AI is listening...");

        const realtimeClient = RealtimeClient.getInstance();
        realtimeClient.socket.dispatchEvent(generateTranscriptionEvent());
        await click("button:contains(Stop Recording)");
        await animationFrame();
        expect(`[data-id='current-transcript-${config.collaboration.peerId}']`).toHaveCount(0);
        expect(".o-ai-transcription-listening").toHaveCount(0);
        expect("[data-embedded-editable='transcriptContent'] blockquote:last-child").toHaveText(
            "This is a test of transcription"
        );
    });

    test.tags("desktop");
    test("should only summarize when there is content in the transcription tab", async () => {
        const transcriptBlock = renderToString("ai.VoiceTranscriptionBlueprint");
        await setupEditor(`<p>[]</p>${transcriptBlock}`, {
            config,
        });

        expect("[data-embedded='voice-transcription']").toHaveCount(1);
        await contains("[data-embedded-editable='summaryContent']", {
            textContent: "",
        });
        expect("button:contains(Summary)").toHaveCount(0);

        await click("button:contains(Start Recording)");
        await click("button:contains(Stop Recording)");
        await contains("[data-embedded-editable='summaryContent']", {
            textContent: "",
        });

        await click("button:contains(Start Recording)");
        await animationFrame();
        const realtimeClient = RealtimeClient.getInstance();
        realtimeClient.socket.dispatchEvent(generateTranscriptionEvent());

        await click("button:contains(Stop Recording)");
        await contains("button.active:contains(Summary)");
        await contains("[data-embedded-editable='summaryContent']", {
            textContent: "This is a response",
        });
    });

    test.tags("desktop");
    test("share composer should have summary content", async () => {
        const transcriptBlock = renderToString("ai.VoiceTranscriptionBlueprint");
        const server = await makeMockServer();
        server.env["mail.compose.message"]._views.form = `
            <form>
                <field name="body" type="html" widget="html_composer_message"/>
            </form>
        `;

        await setupEditor(`<p>[]</p>${transcriptBlock}`, {
            config,
        });

        expect("[data-embedded='voice-transcription']").toHaveCount(1);
        await click("button:contains(Start Recording)");
        await animationFrame();

        const realtimeClient = RealtimeClient.getInstance();
        realtimeClient.socket.dispatchEvent(generateTranscriptionEvent());

        await click("button:contains(Stop Recording)");
        await click("[data-embedded='voice-transcription'] button:contains(Share by email)");
        await animationFrame();
        expect("div[name='body'] p").toHaveText("This is a response");
    });

    test.tags("desktop");
    test("summary has proper prompt actions", async () => {
        onRpc("ai.composer", "retrieve_transcription_composer", () => ({
            ai_agent_id: 1,
            default_prompt: "This is a default prompt",
            available_prompt_ids: [
                {
                    name: "Summarize this prospect call",
                    prompt: "Summarize this prospect call",
                },
                {
                    name: "Write an email recap",
                    prompt: "Write an email recap",
                },
            ],
        }));

        const transcriptBlock = renderToString("ai.VoiceTranscriptionBlueprint");
        const server = await makeMockServer();
        server.env["mail.compose.message"]._views.form = `
        <form>
            <field name="body" type="html" widget="html_composer_message"/>
        </form>
        `;

        await setupEditor(`<p>[]</p>${transcriptBlock}`, {
            config,
        });

        expect("[data-embedded='voice-transcription']").toHaveCount(1);

        await click("button:contains(Start Recording)");
        await animationFrame();
        const realtimeClient = RealtimeClient.getInstance();
        realtimeClient.socket.dispatchEvent(generateTranscriptionEvent());

        await click("button:contains(Stop Recording)");
        await animationFrame();
        expect(
            "[data-embedded='voice-transcription'] button:contains(Summarize this prospect call)"
        ).toHaveCount(1);
        expect(
            "[data-embedded='voice-transcription'] button:contains(Write an email recap)"
        ).toHaveCount(1);
    });

    test.tags("desktop");
    test("can change language on desktop for multi-lingual database", async () => {
        onRpc("res.lang", "get_installed", () => [["en_US"], ["fr_BE"]]);

        const transcriptBlock = renderToString("ai.VoiceTranscriptionBlueprint");
        await setupEditor(`<p>[]</p>${transcriptBlock}`, {
            config,
        });

        expect("[data-embedded='voice-transcription']").toHaveCount(1);
        expect("button.o-dropdown").toHaveText("en");
        await click("button:contains(en)");
        await animationFrame();

        await click("span:contains(fr)");
        await animationFrame();

        expect("button.o-dropdown").toHaveText("fr");
    });

    test.tags("mobile");
    test("test mobile transcription flow", async () => {
        const transcriptBlock = renderToString("ai.VoiceTranscriptionBlueprint");
        await setupEditor(`<p>[]</p>${transcriptBlock}`, {
            config,
        });

        expect("[data-embedded='voice-transcription']").toHaveCount(1);

        await click("button:contains(Notes)");
        await animationFrame();
        expect("span:contains(Notes)").toHaveClass("active");
        await click("span:contains(Notes)");

        await click("button:contains(Start)");

        await click("button:contains(Transcript)");
        await animationFrame();
        expect("span:contains(Transcript)").toHaveClass("active");
        await click("span:contains(Transcript)");

        expect("[data-embedded-editable='transcriptContent'] p>b").toHaveText(getCurrentDate());
        expect(`[data-id='current-transcript-${config.collaboration.peerId}']`).toHaveCount(1);
        expect(".o-ai-transcription-listening").toHaveText("AI is listening...");

        const realtimeClient = RealtimeClient.getInstance();
        realtimeClient.socket.dispatchEvent(generateTranscriptionEvent());
        await click("button:contains(Stop)");
        await animationFrame();
        expect(`[data-id='current-transcript-${config.collaboration.peerId}']`).toHaveCount(0);
        expect(".o-ai-transcription-listening").toHaveCount(0);
        expect("[data-embedded-editable='transcriptContent'] blockquote:last-child").toHaveText(
            "This is a test of transcription"
        );

        expect("button:contains(Summary)").toHaveCount(1);
        await click("button:contains(Summary)");
        await animationFrame();
        expect("span:contains(Summary)").toHaveClass("active");
    });

    test.tags("mobile");
    test("can change language on mobile for multi-lingual database", async () => {
        onRpc("res.lang", "get_installed", () => [["en_US"], ["fr_BE"]]);

        const transcriptBlock = renderToString("ai.VoiceTranscriptionBlueprint");
        await setupEditor(`<p>[]</p>${transcriptBlock}`, {
            config,
        });

        expect("[data-embedded='voice-transcription']").toHaveCount(1);
        await click("button:has(i[data-icon='more_vert'])");
        await animationFrame();
        expect("button:contains(Language)").toHaveText("Language\nen");
        await click("button:contains(Language)");

        await click("span:contains(fr)");
        await click("button:has(i[data-icon='more_vert'])");
        await animationFrame();
        expect("button:contains(Language)").toHaveText("Language\nfr");
    });

    test.tags("mobile");
    test("summary has proper prompt actions in dropdown menu", async () => {
        onRpc("ai.composer", "retrieve_transcription_composer", () => ({
            ai_agent_id: 1,
            default_prompt: "This is a default prompt",
            available_prompt_ids: [
                {
                    name: "Summarize this prospect call",
                    prompt: "Summarize this prospect call",
                },
                {
                    name: "Write an email recap",
                    prompt: "Write an email recap",
                },
            ],
        }));

        const transcriptBlock = renderToString("ai.VoiceTranscriptionBlueprint");
        const server = await makeMockServer();
        server.env["mail.compose.message"]._views.form = `
        <form>
            <field name="body" type="html" widget="html_composer_message"/>
        </form>
        `;

        await setupEditor(`<p>[]</p>${transcriptBlock}`, {
            config,
        });

        expect("[data-embedded='voice-transcription']").toHaveCount(1);

        await click("button:contains(Start)");
        await animationFrame();
        const realtimeClient = RealtimeClient.getInstance();
        realtimeClient.socket.dispatchEvent(generateTranscriptionEvent());

        await click("button:contains(Stop)");
        await animationFrame();

        await click("button:contains(Actions)");
        await animationFrame();
        expect("span.o-dropdown-item:contains(Summarize this prospect call)").toHaveCount(1);
        expect("span.o-dropdown-item:contains(Write an email recap)").toHaveCount(1);
    });
});

describe("Collaboration on transcription component", () => {
    test.tags("desktop");
    test("recording and summarization are synchronized between peers", async () => {
        const peerInfos = await setupMultiEditor({
            peerIds: ["c1", "c2"],
            contentBefore: "<p>[c1}{c1][c2}{c2]<br></p>",
            ...config,
        });

        Object.values(peerInfos).forEach((peer) => {
            peer.editor.config.getRecordInfo = config.getRecordInfo;
        });

        const editor1 = peerInfos.c1.editor;
        const editor2 = peerInfos.c2.editor;

        editor1.shared.dom.insert(
            parseHTML(editor1.document, renderToString("ai.VoiceTranscriptionBlueprint"))
        );
        commit(editor1);

        peerInfos.c2.collaborationPlugin.insertRemoteHistoryCommits(
            peerInfos.c1.historyPlugin.commits
        );
        validateSameHistory(peerInfos);
        cleanHints(editor2);
        expect(editor2.editable.querySelector("[data-embedded='voice-transcription']")).toHaveCount(
            1
        );
        await animationFrame();
        await click(editor1.editable.querySelector("summary>div:last-child button:last-child"));
        await animationFrame();
        peerInfos.c2.collaborationPlugin.insertRemoteHistoryCommits(
            peerInfos.c1.historyPlugin.commits
        );
        expect(
            editor1.editable.querySelector("summary>div:last-child button:last-child")
        ).toHaveText("Stop Recording");
        expect(
            editor2.editable.querySelector("[data-embedded-editable='transcriptContent'] p>b")
        ).toHaveText(getCurrentDate());
        expect(editor2.editable.querySelector(`[data-id='current-transcript-c1']`)).toHaveCount(1);

        const realtimeClient = RealtimeClient.getInstance();
        realtimeClient.socket.dispatchEvent(generateTranscriptionEvent());

        await click(editor1.editable.querySelector("summary>div:last-child button:last-child"));
        await animationFrame();
        peerInfos.c2.collaborationPlugin.insertRemoteHistoryCommits(
            peerInfos.c1.historyPlugin.commits
        );

        expect(editor2.editable.querySelector(`[data-id='current-transcript-c1']`)).toBe(null);
        await click(editor2.editable.querySelector("summary ul.nav button:first-child"));
        await animationFrame();

        expect(
            editor2.editable.querySelector("[data-embedded-editable='summaryContent'] p")
        ).toHaveText("This is a response");
    });
});
