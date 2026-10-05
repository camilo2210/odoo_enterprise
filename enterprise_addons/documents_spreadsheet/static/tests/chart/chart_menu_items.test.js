import { createSpreadsheetFromGraphView } from "@documents_spreadsheet/../tests/helpers/chart_helpers";
import { describe, expect, test } from "@odoo/hoot";
import * as spreadsheet from "@odoo/o-spreadsheet";
import { defineDocumentSpreadsheetModels } from "@documents_spreadsheet/../tests/helpers/data";
import { doMenuAction } from "@spreadsheet/../tests/helpers/ui";
const { topbarMenuRegistry } = spreadsheet.registries;

defineDocumentSpreadsheetModels();
describe.current.tags("desktop");

test("Verify presence of chart in top menu bar in a spreadsheet with a chart", async function () {
    const { model, env } = await createSpreadsheetFromGraphView();
    const sheetId = model.getters.getActiveSheetId();
    const chartId = model.getters.getChartIds(sheetId)[0];

    const root = topbarMenuRegistry.getMenuItems().find((item) => item.id === "data");
    const chartSubmenu = root.children(env).find((c) => c.id === "chart_data_sources");
    expect(chartSubmenu).not.toBe(undefined);
    const chartItem = chartSubmenu.children(env).find((c) => c.id === `item_chart_${chartId}`);
    expect(chartItem).not.toBe(undefined);
    expect(chartItem.name(env)).toBe("(#1) PartnerGraph");
});

test("Chart focus changes on top bar menu click", async function () {
    const { model, env } = await createSpreadsheetFromGraphView();
    const sheetId = model.getters.getActiveSheetId();
    const chartId = model.getters.getChartIds(sheetId)[0];

    env.openSidePanel("ChartPanel");
    expect(model.getters.getSelectedFigureIds()).toEqual([], {
        message: "No chart should be selected",
    });
    await doMenuAction(
        topbarMenuRegistry,
        ["data", "chart_data_sources", `item_chart_${chartId}`],
        env
    );
    const selectedFigureId = model.getters.getSelectedFigureIds()[0];
    expect(model.getters.getChartIdFromFigureId(selectedFigureId)).toBe(chartId, {
        message: "The selected chart should have id " + chartId,
    });
});
