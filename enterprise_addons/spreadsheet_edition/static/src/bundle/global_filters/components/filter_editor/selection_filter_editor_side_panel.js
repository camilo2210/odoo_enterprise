/** @ts-check */

import { AbstractFilterEditorSidePanel } from "./filter_editor_side_panel";
import { FilterEditorFieldMatching } from "./filter_editor_field_matching";
import { ModelSelector } from "@web/core/model_selector/model_selector";
import { ModelFieldSelector } from "@web/core/model_field_selector/model_field_selector";
import { onWillStart, usePlugin, t, useProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { GlobalFilterInput } from "../global_filter_input/global_filter_input";
import { DebugModePlugin } from "@web/core/debug_mode_plugin";

/**
 * This is the side panel to define/edit a global filter of type "selection".
 */
export class SelectionFilterEditorSidePanel extends AbstractFilterEditorSidePanel {
    static template = "spreadsheet_edition.SelectionFilterEditorSidePanel";
    static components = {
        ...AbstractFilterEditorSidePanel.components,
        FilterEditorFieldMatching,
        GlobalFilterInput,
        ModelSelector,
        ModelFieldSelector,
    };

    debugMode = usePlugin(DebugModePlugin);

    selectionProps = useProps({
        model: t.string().optional(),
    });

    setup() {
        super.setup();
        if (this.selectionProps.model) {
            this.store.onSelectionModelSelected({
                technical: this.selectionProps.model,
                label: this.props.label,
            });
        }
        if (this.props.field) {
            this.store.onSelectionFieldSelected(this.props.field.name, this.props.field);
        }
        this.orm = useService("orm");
        onWillStart(async () => {
            if (!this.store.filter.resModel) {
                return;
            }
            const result = await this.orm
                .cache({ type: "disk" })
                .call("ir.model", "display_name_for", [[this.store.filter.resModel]]);
            const label = result[0]?.display_name;
            this.store.updateSelectionModelLabel(label);
        });
    }

    get type() {
        return "selection";
    }

    filterSelectionsFields(field) {
        if (!field.searchable || field.type !== "selection") {
            return false;
        }
        return true;
    }
}
