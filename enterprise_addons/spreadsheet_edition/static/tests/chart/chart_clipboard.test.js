import { describe, expect, test } from "@odoo/hoot";
import { helpers, stores } from "@odoo/o-spreadsheet";
import {
    createSpreadsheetWithChart,
    insertChartInSpreadsheet,
} from "@spreadsheet/../tests/helpers/chart";
import { addGlobalFilter, createBasicChart } from "@spreadsheet/../tests/helpers/commands";
import { defineSpreadsheetModels } from "@spreadsheet/../tests/helpers/data";
import { createSpreadsheetWithPivot } from "@spreadsheet/../tests/helpers/pivot";
import { makeStoreWithModel } from "@spreadsheet/../tests/helpers/stores";

describe.current.tags("headless");
defineSpreadsheetModels();

const { toZone } = helpers;
const { ClipboardStore } = stores;

const chartId = "uuid1";

test("link is kept when copying chart", async () => {
    const { model, pivotId } = await createSpreadsheetWithPivot();
    makeStoreWithModel(model, ClipboardStore);
    createBasicChart(model, chartId);
    model.dispatch("UPDATE_ODOO_LINK_TO_CHART", {
        chartId,
        odooLink: { dataSourceCoreId: pivotId, type: "dataSource", dataSourceType: "pivot" },
    });
    expect(model.getters.getChartOdooLink(chartId)).toEqual({
        dataSourceCoreId: pivotId,
        type: "dataSource",
        dataSourceType: "pivot",
    });
    const figureId = model.getters.getFigureIdFromChartId(chartId);
    model.dispatch("UPDATE_CHART", {
        sheetId: model.getters.getActiveSheetId(),
        chartId,
        figureId,
        definition: {
            ...model.getters.getChartDefinition(chartId),
            type: "line",
        },
    });
    expect(model.getters.getChartOdooLink(chartId)).toEqual({
        dataSourceCoreId: pivotId,
        type: "dataSource",
        dataSourceType: "pivot",
    });
    const sheetId = model.getters.getActiveSheetId();
    model.dispatch("SELECT_FIGURE", { figureId });
    model.dispatch("COPY");
    model.dispatch("PASTE", { target: [toZone("A1")] });
    const chartIds = model.getters.getChartIds(sheetId);
    expect(chartIds.length).toBe(2);
    for (const _chartId of chartIds) {
        expect(model.getters.getChartOdooLink(_chartId)).toEqual({
            dataSourceCoreId: pivotId,
            type: "dataSource",
            dataSourceType: "pivot",
        });
    }
});

test("copy/paste Odoo chart field matching", async () => {
    const { model } = await createSpreadsheetWithChart({ type: "pie" });
    makeStoreWithModel(model, ClipboardStore);
    insertChartInSpreadsheet(model, "bar");
    const sheetId = model.getters.getActiveSheetId();
    const [chartId1, chartId2] = model.getters.getChartIds(sheetId);
    const fieldMatching = {
        chart: {
            [chartId1]: { type: "many2one", chain: "partner_id.company_id" },
            [chartId2]: { type: "many2one", chain: "user_id.company_id" },
        },
    };
    const filterId = "44";
    await addGlobalFilter(
        model,
        {
            id: filterId,
            type: "relation",
            modelName: "res.company",
            label: "Relation Filter",
        },
        fieldMatching
    );
    model.dispatch("SELECT_FIGURE", { figureId: model.getters.getFigureIdFromChartId(chartId2) });
    model.dispatch("COPY");
    model.dispatch("PASTE", { target: [toZone("A1")] });
    const chartIds = model.getters.getChartIds(sheetId);
    expect(model.getters.getOdooChartFieldMatching(chartId1, filterId).chain).toBe(
        "partner_id.company_id"
    );
    expect(model.getters.getOdooChartFieldMatching(chartId2, filterId).chain).toBe(
        "user_id.company_id"
    );
    expect(model.getters.getOdooChartFieldMatching(chartIds[2], filterId).chain).toBe(
        "user_id.company_id"
    );
});

test("cut/paste Odoo chart field matching", async () => {
    const { model } = await createSpreadsheetWithChart({ type: "pie" });
    makeStoreWithModel(model, ClipboardStore);
    insertChartInSpreadsheet(model, "bar");
    const sheetId = model.getters.getActiveSheetId();
    const [chartId1, chartId2] = model.getters.getChartIds(sheetId);
    const fieldMatching = {
        chart: {
            [chartId1]: { type: "many2one", chain: "partner_id.company_id" },
            [chartId2]: { type: "many2one", chain: "user_id.company_id" },
        },
    };
    const filterId = "44";
    await addGlobalFilter(
        model,
        {
            id: filterId,
            type: "relation",
            modelName: "res.company",
            label: "Relation Filter",
        },
        fieldMatching
    );
    model.dispatch("SELECT_FIGURE", { figureId: model.getters.getFigureIdFromChartId(chartId2) });
    model.dispatch("CUT");
    model.dispatch("PASTE", { target: [toZone("A1")] });
    const chartIds = model.getters.getChartIds(sheetId);
    expect(model.getters.getOdooChartFieldMatching(chartId1, filterId).chain).toBe(
        "partner_id.company_id"
    );
    expect(() => model.getters.getChartFieldMatch(chartId2)).toThrow(undefined);
    expect(model.getters.getOdooChartFieldMatching(chartIds[1], filterId).chain).toBe(
        "user_id.company_id"
    );
});
