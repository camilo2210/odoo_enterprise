import { aiSessionIdentifier } from "@ai/utils/ai_session_identifier";
import { Thread } from "@mail/core/common/thread_model";
import { isAiResponseInProgress } from "@ai/discuss/core/common/ai_session_model";
import { patch } from "@web/core/utils/patch";
import { getData } from "@ai/utils/bus_data_getter";
import { fields } from "@mail/model/export";
import { rpc } from "@web/core/network/rpc";

patch(Thread.prototype, {
    setup() {
        super.setup();
        this.ai_agent_id = fields.One("ai.agent");
        this.ai_session_config = {
            ai_prompt_button_ref: null,
        };
    },

    async requestAiSessionAdvance(route, body) {
        const sourceSession = body.session_id
            ? this.store["ai.session"].get(body.session_id)
            : this.channel?.aiRootSession;
        let acknowledgement;
        try {
            acknowledgement = await rpc(route, {
                channel_id: this.id,
                ai_session_identifier: aiSessionIdentifier,
                debug: this.store.debugMode.isActive(),
                current_view_info: await getData("view"),
                ai_session_config: this.channel?.aiSession?.config,
                ...body,
            });
        } catch (error) {
            this.channel.isAiSubmitting = false;
            const session = this.channel?.aiRootSession;
            if (session) {
                session.syncAiSessionState();
            } else {
                this.channel.isAiGenerating = false;
            }
            throw error;
        }
        const currentSession = sourceSession || (!body.session_id && this.channel?.aiRootSession);
        if (currentSession?.exists()) {
            currentSession.loop_state = acknowledgement.loop_state;
        }
        return acknowledgement;
    },

    async post(body, postData = {}, extraData = {}) {
        const hasAiAgent = Boolean(this.channel?.ai_agent_id);
        const pendingRequest =
            !this.channel?.isAiGenerating && this.channel?.aiRootSession?.userInputRequest;
        if (hasAiAgent) {
            this.channel.isAiSubmitting = true;
            this.channel.isAiGenerating = true;
        }
        const { ai_prompt_button_ref, ...extras } = extraData;
        let message;
        try {
            if (pendingRequest) {
                // Preserve the root prompt in history before posting the replacement message.
                await this.requestAiSessionAdvance("/ai/resume_pending_interaction", {
                    session_id: pendingRequest.ai_session_id.id,
                    resume_token: pendingRequest.resumeToken,
                    response: { kind: "skip" },
                });
            }
            message = await super.post(body, postData, extras);
        } catch (error) {
            if (hasAiAgent) {
                this.channel.isAiSubmitting = false;
                this.channel.isAiGenerating = false;
            }
            throw error;
        }
        if (message && hasAiAgent) {
            Object.assign(this.ai_session_config, this.channel?.aiSession?.config);
            this.ai_session_config.ai_prompt_button_ref = ai_prompt_button_ref;
            let loopStateFromAcknowledgement;
            try {
                const acknowledgement = await this.requestAiSessionAdvance(
                    "/ai/start_session_advance",
                    {
                        ai_session_config: this.ai_session_config,
                        mail_message_id: message.id,
                    },
                );
                loopStateFromAcknowledgement = acknowledgement.loop_state;
            } finally {
                this.channel.isAiSubmitting = false;
                const session = this.channel?.aiRootSession;
                const loopState = session?.loop_state ?? loopStateFromAcknowledgement;
                if (session) {
                    session.syncAiSessionState();
                } else {
                    this.channel.isAiGenerating = isAiResponseInProgress(loopState);
                }
            }
        } else if (hasAiAgent) {
            this.channel.isAiSubmitting = false;
            this.channel.isAiGenerating = false;
        }
        return message;
    },
});
