import { GroupConfigMenu } from "@web/views/view_components/group_config_menu";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
* This modifies the group configuration menu by:
* Showing only the "edit_group" option
* Renaming it to "Edit Rule"
* Opening the related data_merge.model form in a dialog
*/
export class DataMergeGroupConfigMenu extends GroupConfigMenu {
    setup() {
        super.setup();
        this.action = useService("action");
    }

    /**
     * @override From super, it returns all the possible configuration options for a group, we want to:
     * Show only "edit_group" action
     * Rename label to "Edit Rule"
    */
    get configItems() {
        return super.configItems
            .filter(item => item.key === "edit_group")
            .map(item => ({ ...item, label: _t("Edit Rule") }));
    }

    /**
     * @override Open the related data_merge.model form in a dialog
     */
    editGroup() {
        const ruleId = this.group.record.data.model_id?.id;
        if (!ruleId) return;

        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "data_merge.model",
            res_id: ruleId,
            views: [[false, "form"]],
            target: "new",
        });
    }
}
