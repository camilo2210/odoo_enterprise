import { Plugin } from "@html_editor/plugin";
import { EMBEDDED_COMPONENT_PLUGINS } from "@html_editor/plugin_sets";
import { selectElements } from "@html_editor/utils/dom_traversal";
import { withSequence } from "@html_editor/utils/resource";
import { _t } from "@web/core/l10n/translation";
import { createElementWithContent } from "@web/core/utils/html";
import { renderToElement } from "@web/core/utils/render";

const RECORDER_SELECTOR = "[data-embedded='voice-transcription']";
const NOTES_CONTENT_SELECTOR = "[data-embedded-editable='notesContent']";
const TRANSCRIPT_CONTENT_SELECTOR = "[data-embedded-editable='transcriptContent']";

export class TranscriptionPlugin extends Plugin {
    static id = "voice-transcription";
    static dependencies = [
        "baseContainer",
        "dom",
        "history",
        "lineBreak",
        "split",
        "embeddedComponents",
    ];

    resources = {
        hints: [
            {
                selector: `${RECORDER_SELECTOR} ${NOTES_CONTENT_SELECTOR}:not(:focus) > *:only-child`,
                text: _t("Add notes about your upcoming meeting"),
            },
            {
                selector: `${RECORDER_SELECTOR} ${TRANSCRIPT_CONTENT_SELECTOR}:not(:focus) > *:only-child`,
                text: _t("Start recording to get a real-time transcript of the conversation"),
            },
        ],
        hint_targets_providers: (_selectionData, editable) => [
            ...editable.querySelectorAll(
                `${RECORDER_SELECTOR} ${NOTES_CONTENT_SELECTOR}:not(:focus) > *:only-child, ${RECORDER_SELECTOR} ${TRANSCRIPT_CONTENT_SELECTOR}:not(:focus) > *:only-child`
            ),
        ],
        user_commands: [
            {
                id: "openTranscriptDialog",
                title: _t("Voice Transcript"),
                description: _t("Dictate text or record a meeting"),
                run: this.insertTranscriptionComponent.bind(this),
            },
        ],
        powerbox_items: [
            {
                keywords: [_t("AI")],
                categoryId: "ai",
                commandId: "openTranscriptDialog",
                icon: "mic",
            },
        ],
        on_will_mount_component_handlers: this.setupTranscriptionComponent.bind(this),
        normalize_processors: withSequence(Infinity, this.normalize.bind(this)),
    };

    setup() {
        super.setup();
        this.peerId = this.config.collaboration?.peerId ?? "";
    }

    get dataId() {
        let id = "current-transcript";
        if (this.peerId !== "") {
            id += `-${this.peerId}`;
        }
        return id;
    }

    insertTranscriptionComponent() {
        const transcriptBlock = renderToElement("ai.VoiceTranscriptionBlueprint");
        this.dependencies.dom.insert(transcriptBlock);
        this.dependencies.history.commit();
    }

    setupTranscriptionComponent({ name, props }) {
        if (name === "voice-transcription") {
            Object.assign(props, {
                onTranscriptionStarted: (component, currentLanguage) =>
                    this.startTranscription(component, currentLanguage),
                onTranscriptionUpdated: (state, transcriptionEditable, textContent) =>
                    this.updateTranscription(state, transcriptionEditable, textContent),
                onSummaryUpdated: (summaryEditable, transcript) =>
                    this.updateSummary(summaryEditable, transcript),
            });
        }
    }

    /**
     * Adds information about the current recording to the transcriptEditable (i.e. the current date).
     *
     * @param {HTMLElement} transcriptionEditable - the editable for the transcription
     * @param {string} currentLanguage - the current language code for the transcription (i.e. en-US)
     */
    startTranscription(transcriptionEditable, currentLanguage) {
        const today = new Date();
        const timeString = today.toLocaleTimeString([currentLanguage], {
            hour: "2-digit",
            minute: "2-digit",
        });

        const textElement = document.createElement("p");
        const boldElement = document.createElement("b");

        boldElement.textContent = `${today.toLocaleDateString()} - ${timeString}`;
        textElement.appendChild(boldElement);
        if (transcriptionEditable.textContent.trim() === "") {
            transcriptionEditable.replaceChildren(textElement);
        } else {
            transcriptionEditable.appendChild(textElement);
        }
        this.cleanupTranscript(transcriptionEditable);
    }

    /**
     * Handles update to the transcription based on recording states.
     *
     * @param {('listening'|'delta'|'completed'|'stopped')} state - the state of the recording.
     * @param {HTMLElement} component - the componente to update.
     * @param {string} textContent - text content to insert into the transcript editable
     */
    updateTranscription(state, component, textContent = "") {
        switch (state) {
            case "listening": {
                this.getOrCreateListeningNode(component);
                this.dependencies.history.commit();
                break;
            }
            case "delta":
                this.updateDelta(component, textContent);
                break;
            case "completed":
                this.commitTranscription(component);
                break;
            case "stopped": {
                this.cleanupTranscript(component);
                break;
            }
        }
    }

    /**
     * Creates or retrieve the "AI is listening..." block.
     *
     * @param {HTMLElement} transcriptEditable the editable where to look for the block.
     */
    getOrCreateListeningNode(transcriptEditable) {
        const currentTranscript = this.getOrCreateTranscriptionItem(transcriptEditable);
        let listeningNode = transcriptEditable.querySelector(".o-ai-transcription-listening");
        if (!listeningNode) {
            listeningNode = document.createElement("span");
            listeningNode.classList.add("o-ai-transcription-listening", "px-1");
            listeningNode.setAttribute("data-oe-protected", "true");
            listeningNode.textContent = _t("AI is listening...");
            currentTranscript.appendChild(listeningNode);
        }
        return listeningNode;
    }

    /**
     * Creates a "current transcript" node and adds it to the transcriptEditable node.
     *
     * @param {HTMLElement} transcriptEditable - the component to insert the transcription into
     * @returns {HTMLElement} the current transcript node
     */
    getOrCreateTranscriptionItem(transcriptEditable) {
        const id = this.dataId;
        let textElement = transcriptEditable.querySelector(`[data-id='${id}']`);
        if (!textElement) {
            textElement = document.createElement("blockquote");
            textElement.setAttribute("data-id", id);
            // HACK: These two attributes are added to prevent a glitch that resets transcript
            // component state on save
            textElement.setAttribute("data-o-mail-quote-node", "1");
            textElement.setAttribute("data-o-mail-quote", "1");
            transcriptEditable.appendChild(textElement);
        }
        return textElement;
    }

    /**
     * Adds a new element to the current transcript block.
     *
     * @param {HTMLElement} component the editable to add the text to.
     * @param {string} textContent the text to add to the current transcript.
     */
    updateDelta(component, textContent) {
        const textElement = this.getOrCreateTranscriptionItem(component);
        const listeningNode = this.getOrCreateListeningNode(component);
        listeningNode.remove();
        textElement.textContent = `${textElement.textContent} ${textContent}`;
        this.dependencies.history.commit();
    }

    /**
     * Commits the current transcript block and removes listening block.
     *
     * @param {HTMLElement} component the editable containing the block to commit.
     */
    commitTranscription(component) {
        const currentTranscript = this.getOrCreateTranscriptionItem(component);
        if (currentTranscript) {
            currentTranscript.removeAttribute("data-id");
        }
        const listeningNode = component.querySelector(".o-ai-transcription-listening");
        listeningNode?.remove();
        this.dependencies.history.commit();
    }

    /**
     * Removes the listening nodes and empty `current-transcript`
     *
     * @param {HTMLElement} transcriptionEditable - the component to perform the cleanup on
     */
    cleanupTranscript(transcriptionEditable) {
        const listeningNode = transcriptionEditable.querySelector(".o-ai-transcription-listening");
        listeningNode?.remove();

        const currentTranscript = transcriptionEditable.querySelector(`[data-id='${this.dataId}']`);
        if (currentTranscript) {
            currentTranscript.removeAttribute("data-id");
        }

        const emptyBlockquotes = transcriptionEditable.querySelectorAll("blockquote");
        let blockRemoved = false;
        emptyBlockquotes.forEach((element) => {
            if (element.textContent.trim() === "") {
                element.remove();
                blockRemoved = true;
            }
        });
        if (blockRemoved) {
            this.dependencies.history.commit();
        }
    }

    /**
     * Replace the content of the summaryEditable by the provided transcript.
     *
     * @param {HTMLElement} summaryEditable - the editable where the summary will be inserted.
     * @param {Markup} transcriptHTML - the html to insert within the summary editable
     */
    updateSummary(summaryEditable, transcriptHTML) {
        summaryEditable.replaceChildren(
            ...createElementWithContent("div", transcriptHTML).children
        );
        this.dependencies.history.commit();
    }

    /**
     * Normalizes transcription components. Will add <br> tags to empty editables.
     *
     * @param {Element} element - the element to normalize
     */
    normalize(element) {
        for (const emptyRecorderNode of selectElements(
            element,
            `${RECORDER_SELECTOR} [data-embedded-editable]:empty`
        )) {
            const baseContainer = this.dependencies.baseContainer.createBaseContainer();
            emptyRecorderNode.replaceChildren(baseContainer);
        }
        return element;
    }
}

EMBEDDED_COMPONENT_PLUGINS.push(TranscriptionPlugin);
