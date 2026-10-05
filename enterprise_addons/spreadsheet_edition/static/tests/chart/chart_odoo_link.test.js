import { describe, test, expect } from "@odoo/hoot";
import { createBasicChart, createSheet, deleteSheet } from "@spreadsheet/../tests/helpers/commands";
import { insertChartInSpreadsheet } from "@spreadsheet/../tests/helpers/chart";
import { defineSpreadsheetModels } from "@spreadsheet/../tests/helpers/data";
import { createSpreadsheetWithPivotAndList } from "@spreadsheet/../tests/helpers/pivot_list";
import { getActionMenu } from "@spreadsheet/../tests/helpers/ui";
import * as spreadsheet from "@odoo/o-spreadsheet";

const { topbarMenuRegistry } = spreadsheet.registries;

describe.current.tags("headless");
defineSpreadsheetModels();

/** @typedef {import("@spreadsheet/o_spreadsheet/o_spreadsheet").Model} Model */

test("Datasources linked to charts are not considered unused", async () => {
    const chartId = "chart_1";
    const { model } = await createSpreadsheetWithPivotAndList();
    const pivotId = model.getters.getPivotIds()[0];
    const listId = model.getters.getListIds()[0];
    const sheetIds = model.getters.getSheetIds();
    createSheet(model, { sheetId: "coucou" });
    sheetIds.forEach((sheetId) => deleteSheet(model, sheetId));
    expect(model.getters.isListUnused(listId)).toBe(true);
    expect(model.getters.isPivotUnused(pivotId)).toBe(true);
    createBasicChart(model, chartId);
    model.dispatch("UPDATE_ODOO_LINK_TO_CHART", {
        chartId,
        odooLink: { type: "dataSource", dataSourceCoreId: pivotId, dataSourceType: "pivot" },
    });
    expect(model.getters.isListUnused(listId)).toBe(true);
    expect(model.getters.isPivotUnused(pivotId)).toBe(false);
    model.dispatch("UPDATE_ODOO_LINK_TO_CHART", {
        chartId,
        odooLink: { type: "dataSource", dataSourceCoreId: listId, dataSourceType: "list" },
    });
    expect(model.getters.isListUnused(listId)).toBe(false);
    expect(model.getters.isPivotUnused(pivotId)).toBe(true);
});

test("Data -> Charts groups chart data sources in a submenu", async () => {
    const { model, env } = await createSpreadsheetWithPivotAndList();
    const chartId = insertChartInSpreadsheet(model, "bar");

    const chartSubmenu = getActionMenu(topbarMenuRegistry, ["data", "chart_data_sources"], env);
    const chartAction = getActionMenu(
        topbarMenuRegistry,
        ["data", "chart_data_sources", `item_chart_${chartId}`],
        env
    );

    expect(chartSubmenu.name(env).toString()).toBe("Charts");
    expect(chartSubmenu.children(env)).toHaveLength(model.getters.getOdooChartIds().length);
    expect(chartAction.name(env).toString()).toBe(model.getters.getOdooChartDisplayName(chartId));
});
