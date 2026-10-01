import { fields, models } from "@web/../tests/web_test_helpers";

export class AISession extends models.ServerModel {
    _name = "ai.session";

    agent_id = fields.Many2one({ relation: "ai.agent" });
    parent_session_id = fields.Many2one({ relation: "ai.session" });
    ai_composer_id = fields.Many2one({ relation: "ai.composer" });
    channel_id = fields.Many2one({ relation: "discuss.channel" });
    res_id = fields.Generic();
    res_model = fields.Generic();
    user_input_request = fields.Generic();
    external_pending_tool = fields.Generic();
    loop_state = fields.Generic({ default: "ready" });
    resume_token = fields.Generic();

    _store_session_fields(res) {
        res.one("agent_id", "_store_agent_fields");
        res.one("parent_session_id", []);
        res.attr("res_model");
        res.attr("res_id");
        res.one("ai_composer_id", "_store_composer_fields");
        res.attr("config", {
            enable_think_longer: false,
            enable_web_search: false,
            enable_resources_only: false,
            auto_confirm: false,
            show_agent_steps: false,
        });
        res.attr("config_rules", {
            enable_web_search: { enable_resources_only: false },
            enable_resources_only: { enable_web_search: false },
        });
        res.attr("userInputRequest", (session) => session.user_input_request || false);
        res.attr("external_pending_tool", (session) => Boolean(session.external_pending_tool));
        res.attr("loop_state");
        res.attr("resume_token");
    }
}
