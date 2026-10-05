import { mailModels } from "@mail/../tests/mail_test_helpers";
import { fields } from "@web/../tests/web_test_helpers";

export class DiscussChannel extends mailModels.DiscussChannel {
    ai_agent_id = fields.Many2one({ relation: "ai.agent" });
    ai_session_ids = fields.One2many({ relation: "ai.session", relation_field: "channel_id" });

    _store_channel_fields(res) {
        super._store_channel_fields(res);
        this._store_ai_fields(res);
    }

    _store_ai_fields(res) {
        const isAiAgentChannel = (c) => this._ai_agent_channel_types().includes(c.channel_type);
        res.one("ai_agent_id", "_store_agent_fields", { predicate: isAiAgentChannel, sudo: true });
        res.many("ai_session_ids", "_store_session_fields", {
            predicate: isAiAgentChannel,
            sudo: true,
        });
        res.one("suggestedAiChannel", [], {
            predicate: (channel) =>
                channel.channel_type === "ai_chat" && !channel.message_ids?.length,
            value: (channel) => this.browse(channel.id)._get_suggested_ai_channel(),
        });
    }

    _get_suggested_ai_channel() {
        return this.env["discuss.channel"].browse();
    }

    _ai_agent_channel_types() {
        return ["ai_chat"];
    }
}
