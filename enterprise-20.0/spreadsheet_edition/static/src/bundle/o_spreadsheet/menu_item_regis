import { _t } from "@web/core/l10n/translation";
import { registries, stores, helpers } from "@odoo/o-spreadsheet";
import {
    REINSERT_DYNAMIC_LIST_CHILDREN,
    REINSERT_STATIC_LIST_CHILDREN,
} from "../list/list_actions";
import {
    REINSERT_DYNAMIC_PIVOT_CHILDREN,
    REINSERT_STATIC_PIVOT_CHILDREN,
    REINSERT_PIVOT_CELL_CHILDREN,
} from "../pivot/pivot_actions";
import { getListHighlights } from "../list/list_highlight_helpers";
import { documentationUrl } from "@web/core/utils/urls";
const { topbarMenuRegistry } = registries;
const { HighlightStore } = stores;
const { UuidGenerator } = helpers;

//--------------------------------------------------------------------------
// Spreadsheet context menu items
//--------------------------------------------------------------------------

topbarMenuRegistry.add("help", {
    name: _t("Help"),
    sequence: 1000,
    isReadonlyAllowed: true,
});

topbarMenuRegistry.addChild("documentation", ["help"], {
    name: _t("Documention"),
    sequence: 1,
    execute: (env) => {
        window.open(documentationUrl("/applications/productivity/spreadsheet/get_started.html"));
    },
    icon: "o-spreadsheet-Icon.QUESTION_CIRCLE",
    isEnabledOnLockedSheet: true,
    isReadonlyAllowed: true,
});

topbarMenuRegistry.addChild("command_palette", ["help"], {
    name: _t("Quick access"),
    sequence: 10,
    execute: (env) => {
        env.openPalette();
    },
    icon: "o-spreadsheet-Icon.KEYBOARD",
    description: "Ctrl+K",
    isReadonlyAllowed: true,
    isEnabledOnLockedSheet: true,
});

topbarMenuRegistry.addChild("new_sheet", ["file"], {
    name: _t("New"),
    sequence: 10,
    isVisible: (env) => env.newSpreadsheet,
    execute: (env) => env.newSpreadsheet(),
    icon: "o-spreadsheet-Icon.NEW",
    isEnabledOnLockedSheet: true,
});

topbarMenuRegistry.addChild("make_copy", ["file"], {
    name: _t("Make a copy"),
    sequence: 20,
    isVisible: (env) => env.makeCopy,
    execute: (env) => env.makeCopy(),
    separator: true,
    icon: "o-spreadsheet-Icon.COPY_FILE",
    isEnabledOnLockedSheet: true,
});

topbarMenuRegistry.addChild("download", ["file"], {
    name: _t("Download"),
    sequence: 40,
    isVisible: (env) => env.download,
    execute: (env) => env.download(),
    isReadonlyAllowed: true,
    icon: "o-spreadsheet-Icon.DOWNLOAD",
    isEnabledOnLockedSheet: true,
});

topbarMenuRegistry.addChild("download_as_json", ["file"], {
    name: _t("Download as JSON"),
    sequence: 50,
    isVisible: (env) => odoo.debug && env.downloadAsJson,
    execute: (env) => env.downloadAsJson(),
    isReadonlyAllowed: true,
    icon: "o-spreadsheet-Icon.DOWNLOAD_AS_JSON",
    isEnabledOnLockedSheet: true,
});

topbarMenuRegistry.addChild("save_as_template", ["file"], {
    name: _t("Save as template"),
    sequence: 70,
    isVisible: (env) => env.saveAsTemplate && env.canSaveAsTemplate(),
    execute: (env) => env.saveAsTemplate(),
    icon: "o-spreadsheet-Icon.SAVE",
    isEnabledOnLockedSheet: true,
});

topbarMenuRegistry.addChild("list_data_sources", ["data"], {
    name: _t("List"),
    sequence: 53,
    icon: "o-spreadsheet-Icon.ODOO_LIST",
    children: [
        (env) => {
            const { getters } = env.model;
            return getters.getListIds().map((listId, sequence) => {
                const highlightProvider = {
                    get highlights() {
                        return getListHighlights(env, listId);
                    },
                };
                return {
                    id: `item_list_${listId}`,
                    name: getters.getListDisplayName(listId),
                    sequence,
                    isReadonlyAllowed: true,
                    execute: () => env.openSidePanel("LIST_PROPERTIES_PANEL", { listId }),
                    onStartHover: () => env.getStore(HighlightStore).register(highlightProvider),
                    onStopHover: () => env.getStore(HighlightStore).unRegister(highlightProvider),
                    isVisible: () => !env.isSmall,
                    isEnabledOnLockedSheet: true,
                };
            });
        },
    ],
});

topbarMenuRegistry.addChild("chart_data_sources", ["data"], {
    name: _t("Charts"),
    sequence: 56,
    icon: "o-spreadsheet-Icon.INSERT_CHART",
    separator: true,
    children: [
        (env) => {
            const { getters } = env.model;
            return getters.getOdooChartIds().map((chartId, sequence) => ({
                id: `item_chart_${chartId}`,
                name: getters.getOdooChartDisplayName(chartId),
                sequence,
                execute: () => {
                    const activeSheetId = getters.getActiveSheetId();
                    const sheetId = getters.getChart(chartId).sheetId;
                    env.model.dispatch("ACTIVATE_SHEET", {
                        sheetIdFrom: activeSheetId,
                        sheetIdTo: sheetId,
                    });
                    env.model.dispatch("SELECT_FIGURE", {
                        figureId: getters.getFigureIdFromChartId(chartId),
                    });
                    env.openSidePanel("ChartPanel");
                },
                isVisible: () => !env.isSmall,
                isEnabled: () => {
                    const sheetId = getters.getChart(chartId).sheetId;
                    return !getters.isSheetLocked(sheetId);
                },
                isEnabledOnLockedSheet: true,
            }));
        },
    ],
});

topbarMenuRegistry.addChild("refresh_data_sources", ["data"], {
    id: "refresh_all_data",
    name: _t("Refresh all data"),
    sequence: 58,
    execute: (env) => {
        env.model.dispatch("REFRESH_ALL_DATA_SOURCES");
    },
    isEnabledOnLockedSheet: true,
    separator: true,
    icon: "o-spreadsheet-Icon.REFRESH_DATA",
});

const reinsertDynamicPivotMenu = {
    id: "reinsert_dynamic_pivot",
    name: _t("Re-insert dynamic pivot"),
    sequence: 60,
    children: [REINSERT_DYNAMIC_PIVOT_CHILDREN],
    isVisible: (env) =>
        env.model.getters.getPivotIds().some((id) => env.model.getters.getPivot(id).isValid()),
    icon: "o-spreadsheet-Icon.INSERT_PIVOT",
};
const reinsertStaticPivotMenu = {
    id: "reinsert_static_pivot",
    name: _t("Re-insert static pivot"),
    sequence: 70,
    children: [REINSERT_STATIC_PIVOT_CHILDREN],
    isVisible: (env) =>
        env.model.getters.getPivotIds().some((id) => env.model.getters.getPivot(id).isValid()),
    icon: "o-spreadsheet-Icon.INSERT_PIVOT",
};

const reinsertPivotCell = {
    id: "reinsert_pivot_cell",
    name: _t("Re-insert pivot cell"),
    sequence: 72,
    children: [REINSERT_PIVOT_CELL_CHILDREN],
    isVisible: (env) =>
        env.model.getters.getPivotIds().some((id) => env.model.getters.getPivot(id).isValid()),
    icon: "o-spreadsheet-Icon.INSERT_PIVOT",
};

const reInsertStaticListMenu = {
    id: "reinsert_static_list",
    name: _t("Re-insert static list"),
    sequence: 74,
    children: [REINSERT_STATIC_LIST_CHILDREN],
    isVisible: (env) =>
        env.model.getters
            .getListIds()
            .some((id) => env.model.getters.getListDataSource(id).isModelValid()),
    icon: "o-spreadsheet-Icon.INSERT_LIST",
};

const reInsertDynamicListMenu = {
    id: "reinsert_dynamic_list",
    name: _t("Re-insert dynamic list"),
    sequence: 74,
    children: [REINSERT_DYNAMIC_LIST_CHILDREN],
    isVisible: (env) =>
        env.model.getters
            .getListIds()
            .some((id) => env.model.getters.getListDataSource(id).isModelValid()),
    icon: "o-spreadsheet-Icon.INSERT_LIST",
};

const insertPivotMenu = {
    name: _t("Pivot table"),
    sequence: 52,
    children: [
        {
            id: "insert_pivot_from_range",
            name: _t("From range"),
            sequence: 1,
            execute: (env) => {
                const pivotId = UuidGenerator.smallUuid();
                const newSheetId = UuidGenerator.smallUuid();
                const result = env.model.dispatch("INSERT_NEW_PIVOT", { pivotId, newSheetId });
                if (result.isSuccessful) {
                    env.openSidePanel("PivotSidePanel", { pivotId });
                }
            },
        },
        {
            id: "insert_pivot_from_odoo_model",
            name: _t("From Odoo data"),
            sequence: 2,
            execute: (env) => {
                env.openSidePanel("NewOdooPivotSidePanel");
            },
        },
    ],
    icon: "o-spreadsheet-Icon.PIVOT",
    isVisible: (env) => !env.isSmall,
};

const insertListMenu = {
    name: _t("Odoo list"),
    sequence: 54,
    execute: (env) => {
        env.openSidePanel("NewOdooListSidePanel");
    },
    icon: "o-spreadsheet-Icon.ODOO_LIST",
    isVisible: (env) => !env.isSmall,
};

topbarMenuRegistry.addChild("reinsert_static_list", ["data"], reInsertStaticListMenu);
topbarMenuRegistry.addChild("reinsert_dynamic_list", ["data"], reInsertDynamicListMenu);
topbarMenuRegistry.replaceChild("reinsert_dynamic_pivot", ["data"], reinsertDynamicPivotMenu);
topbarMenuRegistry.replaceChild("reinsert_static_pivot", ["data"], reinsertStaticPivotMenu);
topbarMenuRegistry.replaceChild("insert_pivot", ["insert"], insertPivotMenu);
topbarMenuRegistry.addChild("reinsert_pivot_cell", ["data"], reinsertPivotCell);
topbarMenuRegistry.addChild("insert_list", ["insert"], insertListMenu);
