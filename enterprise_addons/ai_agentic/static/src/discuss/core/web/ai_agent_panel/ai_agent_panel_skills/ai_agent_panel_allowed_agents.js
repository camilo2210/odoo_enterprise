import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";
import { AiAgentPanelListRenderer } from "@ai_agentic/discuss/core/web/ai_agent_panel/ai_agent_panel_list";

export class AiAgentPanelAgentListRenderer extends AiAgentPanelListRenderer {
    static rowTemplate = "ai_agentic.AiAgentPanelAgentListRenderer.Row";
    static headerTemplate = "ai_agentic.AiAgentPanelAgentListRenderer.Header";
    static empty = {
        icon: "handshake",
        text: _t("Allow this Agent to ask for help to other Agents"),
    };

    async onClickAgent(record) {
        const result = await this.env.services.orm.call("ai.agent", "open_agent_chat", [
            record.data.id,
        ]);
        if (result) {
            this.env.services.action.doAction(result);
        }
    }

    async onClickRemoveAgent(record) {
        await this.activeActions.onDelete?.(record);
    }
}

export class AiAgentX2ManyField extends X2ManyField {
    static components = {
        ...X2ManyField.components,
        ListRenderer: AiAgentPanelAgentListRenderer,
    };
}

registry.category("fields").add("ai_agent_panel_agent_x2many", {
    ...x2ManyField,
    component: AiAgentX2ManyField,
});
