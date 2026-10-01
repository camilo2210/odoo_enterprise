import { aiSessionIdentifier } from "@ai/utils/ai_session_identifier";
import { runAiClientTool } from "@ai/discuss/core/common/ai_client_tool_registry";
import { Record, fields } from "@mail/model/export";

export function isAiResponseInProgress(loopState) {
    return ["waiting_model", "waiting_child", "waiting_client_result"].includes(loopState);
}

export class AiSession extends Record {
    static _name = "ai.session";

    setup() {
        super.setup(...arguments);
        this.onChange(
            () => [this.channel_id, this.loop_state, this.userInputRequest],
            function onChangeAiSessionState() {
                this.syncAiSessionState();
            },
            { immediate: true, initialRun: false },
        );
        this.onChange(
            () => [this.clientToolRequest],
            function onChangeClientToolRequest() {
                this.processPendingClientTool();
            },
            { immediate: true, initialRun: false },
        );
    }

    /** @type {number} */
    id;
    ai_composer_id = fields.One("ai.composer");
    agent_id = fields.One("ai.agent");
    parent_session_id = fields.One("ai.session");
    clientToolRequest = false;
    channel_id = fields.One("discuss.channel", { inverse: "ai_session_ids" });
    loop_state = "ready";
    res_id = undefined;
    res_model = undefined;
    userInputRequest = fields.One("ai.user.input.request");
    external_pending_tool = false;
    resume_token = false;
    config = undefined;
    config_rules = undefined;
    toolStatus = undefined;
    _runningClientToolToken;

    updateConfig(attr, newValue) {
        this.ensureRequiredStates(attr, newValue);
        this.config = {
            ...this.config,
            [attr]: newValue,
        };
    }

    ensureRequiredStates(attr, newValue) {
        if (newValue && this.config_rules[attr]) {
            for (const [key, value] of Object.entries(this.config_rules[attr])) {
                this.config[key] = value;
            }
        }
    }

    syncAiSessionState() {
        const channel = this.channel_id;
        if (!channel) {
            return;
        }
        if (!channel.aiInputSession?.userInputRequest) {
            channel.aiInputSession = channel.ai_session_ids
                .filter((session) => session.userInputRequest)
                .sort((a, b) => a.id - b.id)[0];
        }
        channel.isAiGenerating = Boolean(
            channel.isAiSubmitting ||
                channel.ai_session_ids.some(
                    (session) =>
                        isAiResponseInProgress(session.loop_state) ||
                        (session.parent_session_id &&
                            ["waiting_confirmation", "waiting_answer"].includes(session.loop_state)),
                ),
        );
        this.processPendingClientTool();
    }

    async cancelExternalTool() {
        const resumeToken = this.resume_token;
        const acknowledgement = await this.channel_id.thread.requestAiSessionAdvance(
            "/ai/resume_pending_interaction",
            {
                session_id: this.id,
                resume_token: resumeToken,
                response: { kind: "skip" },
            },
        );
        if (
            acknowledgement.interactionConsumed !== false &&
            this.exists() &&
            this.resume_token === resumeToken
        ) {
            this.external_pending_tool = false;
        }
    }

    async processPendingClientTool() {
        const request = this.clientToolRequest;
        const thread = this.channel_id?.thread;
        if (
            !request ||
            !thread ||
            request.aiSessionIdentifier !== aiSessionIdentifier ||
            this._runningClientToolToken === request.resumeToken
        ) {
            return;
        }
        const resumeToken = request.resumeToken;
        this._runningClientToolToken = resumeToken;
        let response;
        try {
            const result = await runAiClientTool(thread, request);
            response = {
                kind: "client_result",
                value: result === undefined ? "Success" : result,
            };
        } catch (error) {
            response = { kind: "client_error", value: error?.message || String(error) };
        }
        try {
            const acknowledgement = await thread.requestAiSessionAdvance(
                "/ai/resume_pending_interaction",
                {
                    session_id: this.id,
                    response,
                    resume_token: resumeToken,
                },
            );
            if (
                acknowledgement.interactionConsumed !== false &&
                this.exists() &&
                this.clientToolRequest?.resumeToken === resumeToken
            ) {
                this.clientToolRequest = false;
            }
        } catch (error) {
            if (this.exists()) {
                this.store.env.services.notification.add(
                    error?.message || "The AI client tool result could not be submitted.",
                    { type: "danger" },
                );
            }
        } finally {
            if (this._runningClientToolToken === resumeToken) {
                this._runningClientToolToken = undefined;
            }
        }
    }
}

AiSession.register();
