import {
    DocumentsDocument,
    defineDocumentSpreadsheetModels,
    getBasicData,
    getBasicServerData,
} from "@documents_spreadsheet/../tests/helpers/data";
import { makeDocumentsSpreadsheetMockEnv } from "@documents_spreadsheet/../tests/helpers/model";
import { createSpreadsheet } from "@documents_spreadsheet/../tests/helpers/spreadsheet_test_utils";
import {
    animationFrame,
    dblclick,
    describe,
    expect,
    getFixture,
    queryAll,
    test,
    waitFor,
} from "@odoo/hoot";
import * as spreadsheet from "@odoo/o-spreadsheet";
import { insertChartInSpreadsheet } from "@spreadsheet/../tests/helpers/chart";
import { selectCell, setCellContent, setSelection } from "@spreadsheet/../tests/helpers/commands";
import { getCell, getCellValue } from "@spreadsheet/../tests/helpers/getters";
import { doMenuAction } from "@spreadsheet/../tests/helpers/ui";
import { prepareWebClientForSpreadsheet } from "@spreadsheet_edition/../tests/helpers/webclient_helpers";
import {
    contains,
    getService,
    mountWithCleanup,
    onRpc,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";
import { location } from "@web/core/browser/browser";
import { downloadFile } from "@web/core/network/download";
import { WebClient } from "@web/webclient/webclient";

const { topbarMenuRegistry } = spreadsheet.registries;
const { toZone } = spreadsheet.helpers;
const { Model } = spreadsheet;

defineDocumentSpreadsheetModels();
describe.current.tags("desktop");

/** @typedef {import("@spreadsheet/o_spreadsheet/o_spreadsheet").Model} Model */

const TEST_LOCALES = [
    {
        name: "United States",
        code: "en_US",
        thousandsSeparator: ",",
        decimalSeparator: ".",
        dateFormat: "m/d/yyyy",
        timeFormat: "hh:mm:ss a",
        formulaArgSeparator: ",",
    },
    {
        name: "France",
        code: "fr_FR",
        thousandsSeparator: " ",
        decimalSeparator: ",",
        dateFormat: "dd/mm/yyyy",
        timeFormat: "hh:mm:ss",
        formulaArgSeparator: ";",
    },
    {
        name: "Odooland",
        code: "od_OO",
        thousandsSeparator: "*",
        decimalSeparator: ".",
        dateFormat: "yyyy/mm/dd",
        timeFormat: "hh:mm:ss",
        formulaArgSeparator: ",",
    },
];

test("open spreadsheet with deprecated `active_id` params", async function () {
    await prepareWebClientForSpreadsheet();
    onRpc("/spreadsheet/data/documents.document/1", () => expect.step("spreadsheet-loaded"));
    await makeDocumentsSpreadsheetMockEnv({
        serverData: { models: getBasicData() },
    });
    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        type: "ir.actions.client",
        tag: "action_open_spreadsheet",
        params: {
            active_id: 1,
        },
    });
    expect(".o-spreadsheet").toHaveCount(1, {
        message: "It should have opened the spreadsheet",
    });
    expect.verifySteps(["spreadsheet-loaded"]);
});

test("open spreadsheet adds document access token to the URL", async function () {
    await prepareWebClientForSpreadsheet();
    onRpc("/spreadsheet/data/documents.document/2", () => ({
        access_token: "spreadsheetAccessTokeno2",
        data: {},
        has_write_access: true,
        name: "My spreadsheet",
        revisions: [],
    }));
    await makeDocumentsSpreadsheetMockEnv({
        serverData: { models: getBasicData() },
    });
    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        type: "ir.actions.client",
        tag: "action_open_spreadsheet",
        params: {
            spreadsheet_id: 2,
        },
    });
    expect(location.pathname).toBe("/odoo/spreadsheet/spreadsheetAccessTokeno2");
});

test("spreadsheet name remains editable when action is restored from token URL", async function () {
    await prepareWebClientForSpreadsheet();
    onRpc("documents.document", "write", ({ args }) => {
        expect(args).toEqual([[2], { name: "Renamed spreadsheet" }]);
        expect.step("name-written");
        return true;
    });
    onRpc("/spreadsheet/data/documents.document/2", () => ({
        access_token: "spreadsheetAccessTokeno2",
        data: {},
        has_write_access: true,
        name: "My spreadsheet",
        revisions: [],
        writable_rec_name_field: "name",
    }));
    await makeDocumentsSpreadsheetMockEnv({
        serverData: { models: getBasicData() },
    });
    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        type: "ir.actions.client",
        tag: "action_open_spreadsheet",
        params: {
            // The router restores these parameters from a tokenized spreadsheet URL.
            resId: 2,
            access_token: "spreadsheetAccessTokeno2",
        },
    });
    expect(".o_navbar .o_sp_name input").not.toHaveAttribute("disabled");
    await contains(".o_navbar .o_sp_name input").edit("Renamed spreadsheet");
    expect.verifySteps(["name-written"]);
});

test("breadcrumb is rendered the navbar", async function () {
    const actions = {
        2: {
            id: 2,
            name: "Documents",
            res_model: "documents.document",
            type: "ir.actions.act_window",
            views: [[false, "list"]],
        },
    };
    const views = {
        "documents.document,false,list": '<list><field name="name"/></list>',
    };
    const serverData = { actions, models: getBasicData(), views };
    await prepareWebClientForSpreadsheet();
    await makeDocumentsSpreadsheetMockEnv({
        serverData,
    });
    await mountWithCleanup(WebClient);
    await getService("action").doAction(2);
    await getService("action").doAction({
        type: "ir.actions.client",
        tag: "action_open_spreadsheet",
        params: {
            spreadsheet_id: 2,
        },
    });
    expect(".o_navbar .o-sp-breadcrumb").toHaveText("Documents", {
        message: "It should display the breadcrumb",
    });
    expect(".o_navbar .o_sp_name input").toHaveValue("My spreadsheet", {
        message: "It should display the spreadsheet title",
    });
    expect(".o_navbar .o-sp-favorite").toHaveCount(1, {
        message: "It should display the favorite toggle button",
    });
});

test("Can open a spreadsheet in readonly", async function () {
    onRpc("/spreadsheet/data/documents.document/*", () => ({
        data: {},
        name: "name",
        revisions: [],
    }));
    const { model } = await createSpreadsheet();
    expect(model.getters.isReadonly()).toBe(true);
});

test("format menu with default currency", async function () {
    onRpc("/spreadsheet/data/documents.document/*", () => ({
        data: {},
        name: "name",
        revisions: [],
        has_write_access: true,
        default_currency: {
            code: "θdoo",
            symbol: "θ",
            position: "after",
            decimalPlaces: 2,
        },
    }));
    const { model, env } = await createSpreadsheet();
    await doMenuAction(
        topbarMenuRegistry,
        ["format", "format_number", "format_number_currency"],
        env
    );
    expect(getCell(model, "A1").format).toBe("#,##0.00[$θ]");
    await doMenuAction(
        topbarMenuRegistry,
        ["format", "format_number", "format_number_currency_rounded"],
        env
    );
    expect(getCell(model, "A1").format).toBe("#,##0[$θ]");
});

test("dialog window not normally displayed", async function () {
    await createSpreadsheet();
    expect(".o_dialog").toHaveCount(0, { message: "Dialog should not normally be displayed " });
});

test("notify user window", async function () {
    const { env } = await createSpreadsheet();
    env.notifyUser({ text: "this is a notification", type: "warning", sticky: true });
    await animationFrame();
    expect(".o_notification:has(.o_notification_bar.bg-warning)").toHaveText(
        "this is a notification"
    );
});

test("raise error window", async function () {
    const { env } = await createSpreadsheet();
    env.raiseError("this is a message in an opened window that requests user action");
    await animationFrame();
    expect(".o_dialog").toHaveCount(1, { message: "Dialog can be opened" });
    expect(".modal-body p").toHaveText(
        "this is a message in an opened window that requests user action",
        { message: "Can set dialog content" }
    );
    expect(document.querySelector(".o_dialog_error_text")).toBe(null, {
        message: "NotifyUser have no error text",
    });
    expect(document.querySelectorAll(".modal-footer button").length).toBe(1, {
        message: "NotifyUser have 1 button",
    });
});

test("ask confirmation when merging", async function () {
    const { model } = await createSpreadsheet();
    const sheetId = model.getters.getActiveSheetId();
    setCellContent(model, "A2", "hello");
    setSelection(model, "A1:A2");
    await animationFrame();

    await contains(".o-menu-item-button[title='Merge cells']").click();
    expect(".o_dialog").toHaveCount(1, { message: "Dialog should be open" });
    await contains(".o_dialog .btn-secondary").click(); // cancel
    expect(model.getters.isSingleCellOrMerge(sheetId, toZone("A1:A2"))).toBe(false);

    await contains(".o-menu-item-button[title='Merge cells']").click();
    await contains(".o_dialog .btn-primary").click(); // confirm
    expect(model.getters.isSingleCellOrMerge(sheetId, toZone("A1:A2"))).toBe(true);
});

test("Cancel callback of askConfirmation is called when using the cancel button", async function () {
    const { env } = await createSpreadsheet();
    env.askConfirmation(
        "Dialog title",
        () => {},
        () => {
            expect.step("cancel callback");
        }
    );
    await animationFrame();
    expect(".o_dialog .btn-primary").toHaveText("Yes");
    expect(".o_dialog .btn-secondary").toHaveText("No");
    await contains(".o_dialog .btn-secondary").click();
    expect.verifySteps(["cancel callback"]);
});

test("Grid has still the focus after a dialog", async function () {
    const { model, env } = await createSpreadsheet();
    selectCell(model, "F4");
    env.raiseError("Notification");
    await animationFrame();
    await contains(".modal-footer .btn-primary").click();
    await animationFrame();
    expect(".o-grid div.o-composer:first").toBeFocused();
});

test("menu > download as json", async function () {
    let downloadedData = null;
    patchWithCleanup(downloadFile, {
        _download: (data, fileName) => {
            expect.step("download");
            expect(data).toInclude("Hello World");
            expect(data).toInclude("A3");
            expect(fileName).toBe("My spreadsheet.osheet.json");
            downloadedData = data;
        },
    });

    const serverData = getBasicServerData();
    const spreadsheet = DocumentsDocument._records[1];
    spreadsheet.name = "My spreadsheet";
    spreadsheet.spreadsheet_data = JSON.stringify({
        sheets: [{ cells: { A3: "Hello World" } }],
    });

    const { env, model } = await createSpreadsheet({
        spreadsheetId: spreadsheet.id,
        serverData,
    });

    expect(getCellValue(model, "A3")).toBe("Hello World");

    await doMenuAction(topbarMenuRegistry, ["file", "download_as_json"], env);
    expect.verifySteps(["download"]);

    const modelFromLoadedJSON = new Model(JSON.parse(downloadedData));
    expect(getCellValue(modelFromLoadedJSON, "A3")).toBe("Hello World");
});

test("menu > copy", async function () {
    const serverData = getBasicServerData();
    const spreadsheet = DocumentsDocument._records[1];
    spreadsheet.name = "My spreadsheet";
    spreadsheet.spreadsheet_data = JSON.stringify({
        sheets: [{ cells: { A3: "Hello World" } }],
    });

    const { env, model } = await createSpreadsheet({
        spreadsheetId: spreadsheet.id,
        serverData,
        mockRPC: function (_, { method, args, kwargs }) {
            if (method === "copy") {
                expect.step("copy");
                expect(args[0]).toEqual([2]);
                expect(kwargs).toInclude("default");
            }
        },
    });

    expect(getCellValue(model, "A3")).toBe("Hello World");

    await doMenuAction(topbarMenuRegistry, ["file", "make_copy"], env);
    expect.verifySteps(["copy"]);
});

test("Spreadsheet is created with locale in data", async function () {
    const serverData = getBasicServerData();
    serverData.models["documents.document"] = {
        records: [
            {
                id: 3000,
                name: "My template spreadsheet",
                spreadsheet_data: JSON.stringify({ settings: { locale: TEST_LOCALES[1] } }),
            },
        ],
    };

    const { model } = await createSpreadsheet({ serverData, spreadsheetId: 3000 });
    expect(model.getters.getLocale().code).toBe("fr_FR");
});

test("Odoo locales are displayed in setting side panel", async function () {
    const { env } = await createSpreadsheet({
        mockRPC: function (route, { method, model }) {
            if (method === "get_locales_for_spreadsheet") {
                return TEST_LOCALES;
            }
        },
    });

    env.openSidePanel("Settings", {});
    await animationFrame();

    const loadedLocales = [];
    await contains(".o-settings-panel .o-select").click();
    const options = queryAll(".o-spreadsheet .o-select-option");
    for (const option of options) {
        loadedLocales.push(option.dataset.id);
    }

    expect(loadedLocales).toEqual(["en_US", "fr_FR", "od_OO"]);
});

test("sheetName should not be left empty", async function () {
    const fixture = getFixture();
    await createSpreadsheet();

    await dblclick(".o-sheet-list .o-sheet-name");
    await animationFrame();
    expect(".o-sheet-name-editable").toHaveCount(1);

    fixture.querySelector(".o-sheet-list .o-sheet-name").innerText = "";
    await contains(".o-sheet-list .o-sheet-name").press("Enter");
    fixture.querySelector(".modal-dialog");
    expect(".modal-dialog").toBeVisible({ message: "dialog should be visible" });

    await contains(".modal-dialog .btn-primary").click();
    expect(".o-sheet-name-editable").toHaveCount(1);
});

test("Frozen spreadsheet should restrict copy", async function () {
    onRpc("/spreadsheet/data/documents.document/*", () => ({
        data: {},
        name: "name",
        revisions: [],
        handler: "frozen_spreadsheet",
        isReadonly: false,
    }));
    const { model } = await createSpreadsheet();
    expect(model.canDispatch("COPY", {}).isSuccessful).toBe(false);
});

test("datasource links redirect towards the correct views", async function () {
    const { model } = await createSpreadsheet();
    const dataSourceCoreId = insertChartInSpreadsheet(model, "line");
    const chartId = model.getters.getChartIds(model.getters.getActiveSheetId())[0];
    model.dispatch("UPDATE_ODOO_LINK_TO_CHART", {
        chartId,
        odooLink: { type: "dataSource", dataSourceType: "chart", dataSourceCoreId },
    });

    await contains(".o-chart-menu-item[data-id='chartOdooLink']", { visible: false }).click();
    await animationFrame();
    await waitFor(".o_graph_renderer");
    expect(".o_graph_renderer").toHaveCount(1);
    expect(getService("action").currentController.view.type).toBe("graph");
});
