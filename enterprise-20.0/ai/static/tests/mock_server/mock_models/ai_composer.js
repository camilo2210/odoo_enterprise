import { fields, models } from "@web/../tests/web_test_helpers";

export class AIComposer extends models.ServerModel {
    _name = "ai.composer";

    ai_agent_id = fields.Many2one({ relation: "ai.agent" });
    interface_key = fields.Selection({
        selection: [["test_interface_key", "Test Interface Key"]],
    });

    _store_composer_fields(res) {
        res.attr("interface_key");
    }
}
