import { beforeEach, describe, test } from "@odoo/hoot";
import { createBasicChart } from "@spreadsheet/../tests/helpers/commands";
import { defineSpreadsheetModels, getBasicServerData } from "@spreadsheet/../tests/helpers/data";
import { insertChartInSpreadsheet } from "@spreadsheet/../tests/helpers/chart";
import {
    setupCollaborativeEnv,
    spExpect,
} from "@spreadsheet_edition/../tests/helpers/collaborative_helpers";

describe.current.tags("headless");
defineSpreadsheetModels();

/** @typedef {import("@spreadsheet/o_spreadsheet/o_spreadsheet").Model} Model */

let alice, bob, charlie, network;

beforeEach(async () => {
    ({ alice, bob, charlie, network } = await setupCollaborativeEnv(getBasicServerData()));
});

test("Chart link to odoo datasource on figure deletion", async () => {
    const chartId = "1";
    const sheetId = alice.getters.getActiveSheetId();
    createBasicChart(alice, chartId, {}, undefined, "figure1");
    await network.concurrent(() => {
        alice.dispatch("DELETE_FIGURE", { figureId: "figure1", sheetId });
        bob.dispatch("UPDATE_ODOO_LINK_TO_CHART", {
            chartId,
            odooDataSource: { dataSourceCoreId: "pivotId", type: "pivot" },
        });
    });
    spExpect([alice, bob, charlie]).toHaveSynchronizedValue(
        (user) => user.getters.getFigures(sheetId),
        []
    );
    spExpect([alice, bob, charlie]).toHaveSynchronizedValue(
        (user) => user.getters.getChartOdooLink(chartId),
        undefined
    );
});

test("Chart link to odoo datasource on pivot deletion", async () => {
    const chartId = "1";
    const pivotId = "pivotId";
    createBasicChart(alice, chartId);
    await network.concurrent(() => {
        alice.dispatch("REMOVE_PIVOT", { pivotId });
        bob.dispatch("UPDATE_ODOO_LINK_TO_CHART", {
            chartId,
            odooDataSource: { dataSourceCoreId: pivotId, type: "pivot" },
        });
    });
    spExpect([alice, bob, charlie]).toHaveSynchronizedValue(
        (user) => user.getters.getChartOdooLink(chartId),
        undefined
    );
});

test("Chart link to odoo datasource on list deletion", async () => {
    const chartId = "1";
    const listId = "listId";
    createBasicChart(alice, chartId);
    await network.concurrent(() => {
        alice.dispatch("REMOVE_ODOO_LIST", { listId });
        bob.dispatch("UPDATE_ODOO_LINK_TO_CHART", {
            chartId,
            odooDataSource: { dataSourceCoreId: listId, type: "list" },
        });
    });
    spExpect([alice, bob, charlie]).toHaveSynchronizedValue(
        (user) => user.getters.getChartOdooLink(chartId),
        undefined
    );
});

test("Chart link to odoo datasource on odoo chart deletion", async () => {
    const chartId = "1";
    const sheetId = alice.getters.getActiveSheetId();
    createBasicChart(alice, chartId);
    const odooChartId = insertChartInSpreadsheet(alice, "line");
    const figureId = alice.getters.getFigureIdFromChartId(odooChartId);
    await network.concurrent(() => {
        alice.dispatch("DELETE_FIGURE", { figureId, sheetId });
        bob.dispatch("UPDATE_ODOO_LINK_TO_CHART", {
            chartId,
            odooDataSource: { dataSourceCoreId: odooChartId, type: "chart" },
        });
    });
    spExpect([alice, bob, charlie]).toHaveSynchronizedValue(
        (user) => user.getters.getFigures(sheetId).length,
        1
    );
    spExpect([alice, bob, charlie]).toHaveSynchronizedValue(
        (user) => user.getters.getChartOdooLink(chartId),
        undefined
    );
});
