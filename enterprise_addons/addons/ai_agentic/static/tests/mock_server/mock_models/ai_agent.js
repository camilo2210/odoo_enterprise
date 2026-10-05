import { AIAgent } from "@ai/../tests/mock_server/mock_models/ai_agent";

import { patch } from "@web/core/utils/patch";

// Mirrors `ai_agentic/models/ai_agent.py` `open_agent_chat`.

patch(AIAgent.prototype, {
    open_agent_chat(idOrIds) {
        const agent = this.browse(idOrIds)[0];
        const session = this.env["ai.session"]
            ._filter([
                ["agent_id", "=", agent.id],
                ["ai_composer_id", "=", false],
            ])
            .find((session) => {
                const channel = this.env["discuss.channel"].browse(session.channel_id)[0];
                return channel.channel_type === "ai_chat" && !channel.message_ids?.length;
            });
        let channelId = session?.channel_id;
        if (!channelId) {
            channelId = this.browse(agent.id)._create_ai_chat_channel();
            this.env["ai.session"].create({ agent_id: agent.id, channel_id: channelId });
        }
        return {
            type: "ir.actions.client",
            tag: "mail.action_discuss",
            context: {
                active_id: `discuss.channel_${channelId}`,
                scoped_ai_agent_id: agent.id,
            },
        };
    },
});
