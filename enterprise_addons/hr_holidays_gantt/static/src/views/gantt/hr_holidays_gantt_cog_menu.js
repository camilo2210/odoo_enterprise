import { ImportRecords } from "@base_import/import_records/import_records";
import { ExportAll } from "@web/views/list/export_all/export_all";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { exprToBoolean } from "@web/core/utils/strings";
import { STATIC_ACTIONS_GROUP_NUMBER } from "@web/search/action_menus/action_menus";

const cogMenuRegistry = registry.category("cogMenu");

const isLeaveGantt = ({ config, searchModel }) =>
    searchModel.resModel === "hr.leave" && config.viewType === "gantt";

cogMenuRegistry.add(
    "hr-leave-gantt-import",
    {
        Component: ImportRecords,
        groupNumber: STATIC_ACTIONS_GROUP_NUMBER,
        isDisplayed: (env) =>
            !env.services.ui.isSmall &&
            env.config.actionType === "ir.actions.act_window" &&
            isLeaveGantt(env) &&
            exprToBoolean(env.config.viewArch.getAttribute("import"), true) &&
            exprToBoolean(env.config.viewArch.getAttribute("create"), true),
    },
    { sequence: 1 },
);

cogMenuRegistry.add(
    "hr-leave-gantt-export",
    {
        Component: ExportAll,
        groupNumber: STATIC_ACTIONS_GROUP_NUMBER,
        isDisplayed: async (env) =>
            !env.services.ui.isSmall &&
            isLeaveGantt(env) &&
            (await user.hasGroup("base.group_allow_export")) &&
            exprToBoolean(env.config.viewArch.getAttribute("export_xlsx"), true),
    },
    { sequence: 10 },
);
