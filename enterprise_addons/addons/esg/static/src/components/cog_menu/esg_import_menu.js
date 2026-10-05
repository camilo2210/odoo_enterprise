import { ImportRecords } from "@base_import/import_records/import_records";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { STATIC_ACTIONS_GROUP_NUMBER } from "@web/search/action_menus/action_menus";

const cogMenuRegistry = registry.category("cogMenu");

const esgImportRecordsItem = {
    Component: ImportRecords,
    groupNumber: STATIC_ACTIONS_GROUP_NUMBER,
    isDisplayed: async ({ config, searchModel }) => {
        const ui = useService("ui");
        const isEsgModel = searchModel.resModel === "esg.carbon.emission.report";
        const isActionWindow = config.actionType === "ir.actions.act_window";
        return (
            !ui.isSmall &&
            isEsgModel &&
            isActionWindow &&
            ["kanban", "list", "grid"].includes(config.viewType) &&
            user.hasGroup("esg.esg_group_manager")
        );
    },
};

cogMenuRegistry.add("esg-import-menu", esgImportRecordsItem, { sequence: 1 });
