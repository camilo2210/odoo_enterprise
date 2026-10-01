import { Component, onMounted, proxy, signal, t, useListener, useProps } from "@odoo/owl";
import { getActiveHotkey } from "@web/core/hotkeys/hotkey_utils";
import { useService } from "@web/core/utils/hooks";

export class AIUserInputRequest extends Component {
    static template = "ai.UserInputRequest";

    setup() {
        this.store = useService("mail.store");
        this.notification = useService("notification");
        this.props = useProps({
            request: t.instanceOf(this.store["ai.user.input.request"]),
            thread: t.instanceOf(this.store["mail.thread"]),
        });
        this.state = proxy({
            activeIndex: 0,
            freeTextValue: "",
            isSubmitting: false,
            selectedValues: new Set(),
        });
        this.rootRef = signal.ref();
        this.choicesListRef = signal.ref();
        onMounted(() => {
            // Don't steal focus from another chat window, this widget, or a composer
            // where the user has already started typing.
            requestAnimationFrame(() => {
                const ownChatWindowEl = this.rootRef()?.closest(
                    ".o-mail-ChatWindow, .o-mail-DiscussContent",
                );
                const active = document.activeElement;
                const focusIsOutsideChatWindow =
                    active && ownChatWindowEl && !ownChatWindowEl.contains(active);
                const focusIsAlreadyOnThisWidget = Boolean(this.choicesListRef()?.contains(active));
                const hasComposerDraft = active?.matches(".o-mail-Composer-input") && active.value;
                if (!focusIsOutsideChatWindow && !focusIsAlreadyOnThisWidget && !hasComposerDraft) {
                    this.choicesListRef()?.querySelector("button")?.focus();
                }
            });
        });

        useListener(
            () => this.rootRef(),
            "click",
            (ev) => {
                if (this.choicesListRef()?.contains(ev.target)) {
                    return;
                }
                this.focusActiveRow();
            },
        );
    }

    get isConfirmation() {
        return this.props.request?.type === "confirmation";
    }

    get rows() {
        const choices = this.props.request?.choices ?? [];
        const rows = choices.map((data) => ({ type: "option", data }));
        if (this.props.request?.allowFreeText) {
            rows.push({ type: "text" });
        }
        return rows;
    }

    get activeRow() {
        return this.rows[this.state.activeIndex];
    }

    get isFreeTextSelected() {
        return Boolean(this.state.freeTextValue.trim());
    }

    get selectedCount() {
        return this.state.selectedValues.size + (this.isFreeTextSelected ? 1 : 0);
    }

    get areChoicesDisabled() {
        return !this.props.request?.multiSelect && this.isFreeTextSelected;
    }

    get showSkip() {
        return Boolean(this.props.request) && !this.isConfirmation;
    }

    get freeTextInput() {
        return this.choicesListRef()?.querySelector("input[type=text]") ?? null;
    }

    isRowSelected(row) {
        return row.type === "text"
            ? this.isFreeTextSelected
            : this.state.selectedValues.has(row.data.value);
    }

    onRowSelect(row) {
        const inputRequest = this.props.request;
        if (!inputRequest || !row) {
            return;
        }
        if (row.type === "text") {
            this.freeTextInput?.focus();
            return;
        }
        if (inputRequest.multiSelect) {
            const { value } = row.data;
            if (this.state.selectedValues.has(value)) {
                this.state.selectedValues.delete(value);
            } else {
                this.state.selectedValues.add(value);
            }
            return;
        }
        this.submitAnswer([row.data.value], inputRequest);
    }

    submitFreeText() {
        const inputRequest = this.props.request;
        const value = this.state.freeTextValue.trim();
        if (!inputRequest || !value) {
            return;
        }
        this.submitAnswer([value], inputRequest);
    }

    confirmMultiSelect() {
        const inputRequest = this.props.request;
        if (!inputRequest) {
            return;
        }
        const selected = inputRequest.choices.filter((o) => this.state.selectedValues.has(o.value));
        const freeText = this.state.freeTextValue.trim();
        if (!selected.length && !freeText) {
            return;
        }
        const values = [...selected.map((o) => o.value), ...(freeText ? [freeText] : [])];
        this.submitAnswer(values, inputRequest);
    }

    async skip() {
        const inputRequest = this.props.request;
        if (!inputRequest) {
            return;
        }
        await this.submitPendingInteractionResponse(inputRequest, { kind: "skip" });
    }

    async submitPendingInteractionResponse(inputRequest, response) {
        if (this.state.isSubmitting) {
            return;
        }
        this.state.isSubmitting = true;
        const session = inputRequest.ai_session_id;
        const resumeToken = inputRequest.resumeToken;
        try {
            const acknowledgement = await this.props.thread.requestAiSessionAdvance(
                "/ai/resume_pending_interaction",
                {
                    session_id: session.id,
                    response,
                    resume_token: resumeToken,
                },
            );
            if (acknowledgement.interactionConsumed !== false) {
                if (session.userInputRequest?.resumeToken === resumeToken) {
                    session.userInputRequest = undefined;
                }
                if (!this.props.thread.channel.aiInputSession?.userInputRequest) {
                    this.props.thread.composer.autofocus++;
                }
            }
        } catch (error) {
            this.notification.add(error?.message || "The AI interaction could not be submitted.", {
                type: "danger",
            });
        } finally {
            this.state.isSubmitting = false;
        }
    }

    async submitAnswer(values, inputRequest) {
        const response =
            inputRequest.type === "confirmation"
                ? { kind: "confirmation", value: values[0] }
                : { kind: "question", value: values };
        await this.submitPendingInteractionResponse(inputRequest, response);
    }

    /** Restore focus to whatever row is active (used when the surrounding prompt is clicked). */
    focusActiveRow() {
        const list = this.choicesListRef();
        if (!list) {
            return;
        }
        if (this.activeRow?.type === "text") {
            list.querySelector("input[type=text]")?.focus();
            return;
        }
        list.querySelectorAll("button")?.[this.state.activeIndex]?.focus();
    }

    activateRow(index) {
        this.state.activeIndex = index;
        this.focusActiveRow();
    }

    onChoicesKeydown(ev) {
        const rows = this.rows;
        if (rows.length <= 1) {
            return;
        }
        const isTextInput = ev.target === this.freeTextInput;
        const hotkey = getActiveHotkey(ev);
        switch (hotkey) {
            case "space":
                if (isTextInput) {
                    return;
                }
                break;
            case "arrowdown":
                if (isTextInput && this.areChoicesDisabled) {
                    return;
                }
                this.activateRow(Math.min(this.state.activeIndex + 1, rows.length - 1));
                break;
            case "arrowup":
                if (isTextInput && this.areChoicesDisabled) {
                    return;
                }
                this.activateRow(Math.max(this.state.activeIndex - 1, 0));
                break;
            case "enter":
                if (isTextInput && this.isFreeTextSelected && !this.props.request?.multiSelect) {
                    this.submitFreeText();
                } else {
                    this.onRowSelect(this.activeRow);
                }
                break;
            default: {
                if (isTextInput) {
                    return;
                }
                // Number shortcuts jump straight to a choice (single-select only).
                const index = Number(hotkey) - 1;
                const row = rows[index];
                if (this.props.request.multiSelect || row?.type !== "option") {
                    return;
                }
                this.activateRow(index);
                this.onRowSelect(row);
            }
        }
        ev.preventDefault();
        ev.stopPropagation();
    }
}
