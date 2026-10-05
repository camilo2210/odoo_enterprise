import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";
import { AiAgentPanelListRenderer } from "@ai_agentic/discuss/core/web/ai_agent_panel/ai_agent_panel_list";

export class AiAgentPanelSkillListRenderer extends AiAgentPanelListRenderer {
    static rowTemplate = "ai_agentic.AiAgentPanelSkillListRenderer.Row";
    static headerTemplate = "ai_agentic.AiAgentPanelSkillListRenderer.Header";
    static empty = {
        icon: "wand_stars",
        text: _t("Add skills to expand what your agent can do."),
    };

    async onClickEditSkill(record) {
        await this.props.openRecord(record);
    }

    async onClickRemoveSkill(record) {
        await this.activeActions.onDelete?.(record);
    }
}

export class AiAgentSkillX2ManyField extends X2ManyField {
    static components = {
        ...X2ManyField.components,
        ListRenderer: AiAgentPanelSkillListRenderer,
    };
}

registry.category("fields").add("ai_agent_panel_skill_x2many", {
    ...x2ManyField,
    component: AiAgentSkillX2ManyField,
});
