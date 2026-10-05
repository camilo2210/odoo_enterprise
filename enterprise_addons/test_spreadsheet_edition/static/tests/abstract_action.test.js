import { describe, expect, test } from "@odoo/hoot";
import { animationFrame, rightClick, runAllTimers, waitFor } from "@odoo/hoot-dom";
import { EventBus } from "@odoo/owl";

import { helpers, registries } from "@odoo/o-spreadsheet";
import { WebClient } from "@web/webclient/webclient";

import {
    addGlobalFilter,
    setCellContent,
    setGlobalFilterValue,
} from "@spreadsheet/../tests/helpers/commands";
import { doMenuAction } from "@spreadsheet/../tests/helpers/ui";
import { insertPivot } from "@spreadsheet_edition/../tests/helpers/collaborative_helpers";
import { AbstractSpreadsheetAction } from "@spreadsheet_edition/bundle/actions/abstract_spreadsheet_action";
import {
    defineTestSpreadsheetEditionModels,
    SpreadsheetTest,
} from "@test_spreadsheet_edition/../tests/helpers/data";
import { createSpreadsheetTestAction } from "@test_spreadsheet_edition/../tests/helpers/helpers";
import {
    contains,
    getService,
    mockService,
    mountWithCleanup,
    onRpc,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";
import { router } from "@web/core/browser/router";
import { getDummyBasicServerData } from "./helpers/data";

const { cellMenuRegistry, topbarMenuRegistry } = registries;
const { toZone } = helpers;

defineTestSpreadsheetEditionModels();

test("custom colors in color picker", async function () {
    onRpc("/spreadsheet/data/*", () => ({
        data: {},
        name: "test",
        company_colors: ["#875A7B", "not a valid color"],
    }));
    const { model } = await createSpreadsheetTestAction("spreadsheet_test_action");
    expect(model.getters.getCustomColors()).toEqual(["#875A7B"]);
});

test.tags("desktop");
test("preserve global filters when navigating through breadcrumb", async function () {
    const { model, env } = await createSpreadsheetTestAction("spreadsheet_test_action");
    await insertPivot(model);
    setCellContent(model, "A1", '=PIVOT.VALUE(1, "probability")');
    await addGlobalFilter(model, {
        id: "42",
        type: "relation",
        label: "Relation Filter",
        modelName: "product",
    });
    await setGlobalFilterValue(model, {
        id: "42",
        value: { operator: "in", ids: [37] },
    });
    await doMenuAction(cellMenuRegistry, ["pivot_see_records"], env);
    expect(".o_list_renderer").toHaveCount(1);
    await contains(".o_back_button").click();
    await contains(".o_topbar_filter_icon").click();
    expect(".o_multi_record_selector").toHaveText("xphone");
});

test("receives collaborative messages when action is restored", async function () {
    const mockBusService = {
        _bus: new EventBus(),
        subscribe(eventName, handler) {
            this._bus.addEventListener("notif", ({ detail }) => {
                if (detail.type === eventName) {
                    handler(detail.payload);
                }
            });
        },
        notify(message) {
            this._bus.trigger("notif", message);
        },
    };
    mockService("bus_service", mockBusService);
    const spreadsheetData = {
        sheets: [
            {
                id: "sheet1",
                cells: {
                    A1: '=PIVOT.VALUE(1, "probability:sum")',
                },
            },
        ],
        pivots: {
            1: {
                type: "ODOO",
                columns: [],
                rows: [],
                domain: [],
                measures: [{ id: "probability:sum", fieldName: "probability", aggregator: "sum" }],
                model: "partner",
            },
        },
    };
    const spreadsheetId = 1;
    SpreadsheetTest._records = [
        {
            id: spreadsheetId,
            name: "my test spreadsheet",
            spreadsheet_data: JSON.stringify(spreadsheetData),
        },
    ];
    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        type: "ir.actions.client",
        tag: "spreadsheet_test_action",
        params: {
            spreadsheet_id: 1,
            res_model: "spreadsheet.test",
        },
    });
    await animationFrame();
    await rightClick(".o-grid-overlay", { position: "top-left" });
    await animationFrame();
    await contains('.o-menu-item[data-name="pivot_see_records"]').click();
    await waitFor(".o_list_renderer");
    const revisionWebSocketMessage = {
        id: spreadsheetId,
        type: "REMOTE_REVISION",
        version: 1,
        serverRevisionId: "START_REVISION",
        nextRevisionId: "2",
        clientId: "raoul",
        commands: [
            {
                type: "SET_FORMATTING",
                sheetId: "sheet1",
                target: [toZone("A1")],
                style: { bold: true },
            },
        ],
    };
    // simulate a collaborative revision by pushing the revision
    // to the websocket bus.
    getService("bus_service").notify({
        id: spreadsheetId,
        type: "spreadsheet",
        payload: revisionWebSocketMessage,
    });
    await animationFrame();
    await contains(".o_back_button").click();
    expect('.o-menu-item-button[title="Bold (Ctrl+B)"]').toHaveClass("active");
});

test("The geoJson service is given to the model for geo charts", async function () {
    const mockGeoJson = {
        type: "FeatureCollection",
        features: [{ type: "Feature", id: "BE", properties: { name: "Belgium" }, geometry: {} }],
    };
    onRpc("/spreadsheet/static/topojson/world.topo.json", () => mockGeoJson);
    const { model } = await createSpreadsheetTestAction("spreadsheet_test_action", {});

    expect(model.getters.getGeoChartAvailableRegions().map((r) => r.label)).toEqual([
        "World",
        "Africa",
        "Asia",
        "Europe",
        "North America",
        "United States",
        "South America",
        "Oceania",
    ]);

    expect(model.getters.getGeoJsonFeatures("world")).toEqual(undefined);
    await runAllTimers();
    expect(model.getters.getGeoJsonFeatures("world")).toEqual([
        {
            type: "Feature",
            id: "BE",
            properties: { name: "Belgium" },
            geometry: {},
        },
    ]);
});

describe("sheetId router synchronization", () => {
    function mockRouter(initialState = {}) {
        const routerState = { ...initialState };
        patchWithCleanup(router, {
            get current() {
                return routerState;
            },
            pushState(state) {
                Object.assign(routerState, state);
            },
            replaceState(state) {
                Object.assign(routerState, state);
            },
        });
        return routerState;
    }
    async function createTestSpreadsheet() {
        const spreadsheetId = 1;
        const serverData = getDummyBasicServerData();
        serverData.models["spreadsheet.test"].records = [
            {
                name: "Untitled Dummy Spreadsheet",
                spreadsheet_data: JSON.stringify({
                    sheets: [
                        { id: "sheet1", name: "Sheet1" },
                        { id: "sheet2", name: "Sheet2" },
                    ],
                }),
                id: spreadsheetId,
            },
        ];
        const { model, env } = await createSpreadsheetTestAction("spreadsheet_test_action", {
            serverData,
            spreadsheetId,
        });
        return { model, env };
    }

    test("activates sheet from router on initialization", async () => {
        mockRouter({ sid: "sheet2" });
        const { model } = await createTestSpreadsheet();
        expect(model.getters.getActiveSheetId()).toBe("sheet2");
    });

    test("falls back to first sheet and syncs router when sid is invalid", async () => {
        const routerState = mockRouter({ sid: "invalid" });
        const { model } = await createTestSpreadsheet();
        expect(model.getters.getActiveSheetId()).toBe("sheet1");
        expect(routerState.sid).toBe("sheet1");
    });

    test("falls back to first sheet and sets router when sid is absent", async () => {
        const routerState = mockRouter();
        const { model } = await createTestSpreadsheet();
        expect(model.getters.getActiveSheetId()).toBe("sheet1");
        expect(routerState.sid).toBe("sheet1");
    });

    test("syncs router when active sheet changes", async () => {
        const routerState = mockRouter();
        const { model } = await createTestSpreadsheet();
        expect(routerState.sid).toBe("sheet1");
        model.dispatch("ACTIVATE_SHEET", {
            sheetIdFrom: "sheet1",
            sheetIdTo: "sheet2",
        });
        expect(routerState.sid).toBe("sheet2");
    });

    test("updates router when the active sheet is deleted", async () => {
        const routerState = mockRouter();
        const { model } = await createTestSpreadsheet();
        expect(routerState.sid).toBe("sheet1");
        model.dispatch("DELETE_SHEET", {
            sheetId: "sheet1",
            sheetName: "Sheet1",
        });
        expect(model.getters.getActiveSheetId()).toBe("sheet2");
        expect(routerState.sid).toBe("sheet2");
    });

    test("preserve sid when navigating through breadcrumb", async function () {
        const routerState = mockRouter({ sid: "sheet2" });
        const { model, env } = await createTestSpreadsheet();
        expect(model.getters.getActiveSheetId()).toBe("sheet2");

        await insertPivot(model, "sheet2");
        setCellContent(model, "A1", '=PIVOT.VALUE(1, "probability:sum")', "sheet2");
        await doMenuAction(cellMenuRegistry, ["pivot_see_records"], env);
        expect(".o_list_renderer").toHaveCount(1);

        await contains(".o_back_button").click();
        expect(model.getters.getActiveSheetId()).toBe("sheet2");
        expect(routerState.sid).toBe("sheet2");
    });
});

test("The action should redirect to the home menu and not sync the sid when access is denied", async function () {
    onRpc("/spreadsheet/data/*", () => {
        expect.step("try-open-spreadsheet");
        throw new Response("", { status: 403 });
    });
    mockService("action", {
        async doAction(actionRequest) {
            if (actionRequest === "menu") {
                expect.step("redirect-to-home-menu");
                return;
            }
            return super.doAction(...arguments);
        },
    });
    patchWithCleanup(AbstractSpreadsheetAction.prototype, {
        syncSheetFromRouter() {
            expect.step("sync-sheet-from-router")
            return super.syncSheetFromRouter(...arguments);
        },
    });
    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        type: "ir.actions.client",
        tag: "spreadsheet_test_action",
        params: {
            spreadsheet_id: 1,
        },
    }).catch(() => {});
    expect.verifySteps(["try-open-spreadsheet", "redirect-to-home-menu"]);
});

test("The action should redirect to the home menu when the related record cannot be found", async function () {
    const menuDef = Promise.withResolvers();
    onRpc("/spreadsheet/data/*", () => {
        expect.step("try-open-spreadsheet");
        throw new Response("", { status: 404 });
    });
    mockService("action", {
        async doAction(actionRequest) {
            if (actionRequest === "menu") {
                expect.step("redirect-to-home-menu");
                menuDef.resolve();
            }
            return super.doAction(...arguments);
        },
    });
    await mountWithCleanup(WebClient);
    getService("action")
        .doAction({
            type: "ir.actions.client",
            tag: "spreadsheet_test_action",
            params: {
                spreadsheet_id: 1,
            },
        })
        .catch(() => {});
    await menuDef.promise;
    expect.verifySteps(["try-open-spreadsheet", "redirect-to-home-menu"]);
});


test("Can open the command palette from the topbar menu", async function () {
  const { env } = await createSpreadsheetTestAction("spreadsheet_test_action");
  await doMenuAction(
      topbarMenuRegistry,
      ["help", "command_palette"],
      env
  );
  await animationFrame();
  expect(".o_command_palette").toHaveCount(1);
})
