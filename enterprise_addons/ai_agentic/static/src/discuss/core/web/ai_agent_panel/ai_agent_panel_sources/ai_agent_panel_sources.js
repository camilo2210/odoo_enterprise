import { AgentSourceAddDialog } from "@ai_agentic/components/agent_add_source_dialog/agent_add_source_dialog";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { BooleanToggleField } from "@web/views/fields/boolean_toggle/boolean_toggle_field";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";
import { AiAgentPanelListRenderer } from "@ai_agentic/discuss/core/web/ai_agent_panel/ai_agent_panel_list";
import { AiAgentSourceRow } from "@ai_agentic/discuss/core/web/ai_agent_panel/ai_agent_panel_sources/ai_agent_source_row";
import { AiAgentSourceFolderTreePlugin } from "@ai_agentic/discuss/core/web/ai_agent_panel/ai_agent_panel_sources/ai_agent_source_folder_tree_plugin";

import { onWillStart, providePlugins, usePlugin } from "@odoo/owl";

export class AiAgentPanelSourceListRenderer extends AiAgentPanelListRenderer {
    static rowTemplate = "ai_agentic.AiAgentPanelSourceListRenderer.Row";
    static headerTemplate = "ai_agentic.AiAgentPanelSourceListRenderer.Header";
    static empty = {
        icon: "folder_open",
        text: _t("Add sources to give your agent the information it needs to answer accurately."),
    };
    static components = {
        ...AiAgentPanelListRenderer.components,
        AiAgentSourceRow,
        BooleanToggleField,
    };

    setup() {
        super.setup();
        this.sourcesFolderTree = usePlugin(AiAgentSourceFolderTreePlugin);
    }
}

export class AiAgentSourceX2ManyField extends X2ManyField {
    static components = {
        ...X2ManyField.components,
        ListRenderer: AiAgentPanelSourceListRenderer,
    };

    setup() {
        super.setup();
        this.dialog = useService("dialog");
        providePlugins([AiAgentSourceFolderTreePlugin], {
            record: this.props.record,
            list: this.list,
        });
        this.sourcesFolderTree = usePlugin(AiAgentSourceFolderTreePlugin);
        onWillStart(() => this.sourcesFolderTree.loadTree());
    }

    get rendererProps() {
        return {
            ...super.rendererProps,
            list: { records: this.sourcesFolderTree.rootRecords },
        };
    }

    get canCreate() {
        return super.canCreate && this.sourcesFolderTree.canManageSources();
    }

    onAdd() {
        this.dialog.add(AgentSourceAddDialog, {
            agentId: this.props.record.resId,
            onSourcesAdded: () => this.sourcesFolderTree.reloadAll(),
        });
    }
}

registry.category("fields").add("ai_agent_panel_source_x2many", {
    ...x2ManyField,
    component: AiAgentSourceX2ManyField,
});
