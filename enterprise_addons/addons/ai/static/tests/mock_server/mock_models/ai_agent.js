import { Store } from "@mail/../tests/mock_server/store";

import { Command, fields, models } from "@web/../tests/web_test_helpers";

export class AIAgent extends models.ServerModel {
    _name = "ai.agent";

    name = fields.Char();
    allowed_agent_ids = fields.Many2many({ relation: "ai.agent" });
    partner_id = fields.Many2one({
        relation: "res.partner",
    });
    subtitle = fields.Char();
    image_128 = fields.Binary();
    system_prompt = fields.Text();
    sources_ids = fields.One2many({
        relation: "ai.agent.source",
        relation_field: "ai_agent_id",
    });

    _store_agent_fields(res) {
        res.extend(["partner_id", "subtitle", "name"]);
        // Python derives xml_id from ir.model.data; test agents are created without one, so it
        // resolves to false (ir.model.data is not mocked).
        res.attr("xml_id", false);
        res.attr("sources_ids");
    }

    action_launch_ai_chat(interface_key, res_model = null, res_id = null) {
        const agentPartnerId = this.env["res.partner"].create({ name: "Test AI Agent" });
        const agent = this.env["ai.agent"].browse(
            this.env["ai.agent"].create({ name: "Test AI Agent", partner_id: agentPartnerId }),
        );
        const channel = this.env["discuss.channel"].browse(agent._create_ai_chat_channel());
        const composer = this.env["ai.composer"].browse(
            this.env["ai.composer"].create({ interface_key }),
        );
        this.env["ai.session"].create({
            agent_id: agent[0].id,
            ai_composer_id: composer[0].id,
            channel_id: channel[0].id,
            res_model: res_model || false,
            res_id: res_id || false,
        });
        const store = new Store();
        store.add(channel, (res) => {
            res.attr("are_prompts_from_local_storage", false);
            res.from_method("_store_channel_fields");
        });
        return {
            ai_channel_id: channel[0].id,
            data: store.as_dict(),
            model_has_thread: null,
        };
    }

    /** @param {import("@mail/../tests/mock_server/mock_models/res_partner").ResPartner} partner */
    _create_ai_chat_channel() {
        const agent = this[0];
        return this.env["discuss.channel"].create({
            name: agent.name,
            channel_type: "ai_chat",
            channel_member_ids: [
                Command.create({
                    partner_id: this.env.user.partner_id,
                }),
                Command.create({
                    partner_id: agent.partner_id,
                }),
            ],
            ai_agent_id: agent.id,
        });
    }
}

export class AIAgentSource extends models.ServerModel {
    _name = "ai.agent.source";

    ai_agent_id = fields.Many2one({ relation: "ai.agent" });
    name = fields.Char();
}
