import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";
import { AiAgentPanelListRenderer } from "@ai_agentic/discuss/core/web/ai_agent_panel/ai_agent_panel_list";
import { AgentTriggerAddDialog } from "@ai_agentic/components/agent_add_trigger_dialog/agent_add_trigger_dialog";

export class AiAgentPanelTriggerListRenderer extends AiAgentPanelListRenderer {
    static rowTemplate = "ai_agentic.AiAgentPanelTriggerListRenderer.Row";
    static empty = {
        icon: "flash_on",
        text: _t(
            "Add triggers to let your agent run automatically on a schedule or when key events happen."
        ),
    };

    setup() {
        super.setup();
        this.action = useService("action");
        this.orm = useService("orm");
        this.notification = useService("notification");
    }

    isCronTrigger(record) {
        return record.data.model_name === "ai.automation.trigger";
    }

    async onClickOpenTrigger(record) {
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "base.automation",
            res_id: record.data.id,
            views: [[false, "form"]],
        });
    }

    async onToggleActive(record, isActive) {
        await this.orm.write("base.automation", [record.data.id], { active: isActive });
        await this.props.list.model.load();
    }

    async onClickRunTrigger(record) {
        this.notification.add(_t("Automation triggered!"), { type: "success" });
        await this.orm.call("base.automation", "action_ai_run_now", [record.data.id]);
    }
}

export class AiAgentTriggerX2ManyField extends X2ManyField {
    static components = {
        ...X2ManyField.components,
        ListRenderer: AiAgentPanelTriggerListRenderer,
    };

    setup() {
        super.setup();
        this.dialog = useService("dialog");
    }

    onAdd() {
        this.dialog.add(AgentTriggerAddDialog, { agentId: this.props.record.resId });
    }
}

registry.category("fields").add("ai_agent_panel_trigger_x2many", {
    ...x2ManyField,
    component: AiAgentTriggerX2ManyField,
});
