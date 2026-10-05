import {
    defineDocumentSpreadsheetModels,
    getBasicData,
} from "@documents_spreadsheet/../tests/helpers/data";
import { beforeEach, describe, expect, getFixture, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { contains, serverState } from "@web/../tests/web_test_helpers";
import { createSpreadsheet } from "@documents_spreadsheet/../tests/helpers/spreadsheet_test_utils";
import { createSpreadsheetWithPivot } from "@documents_spreadsheet/../tests/helpers/pivot_helpers";
import { createSpreadsheetWithList } from "@spreadsheet/../tests/helpers/list";
import { mountSpreadsheet } from "@spreadsheet/../tests/helpers/ui";
import { createSpreadsheetWithPivotAndList } from "@spreadsheet/../tests/helpers/pivot_list";
import { insertChartInSpreadsheet } from "@spreadsheet/../tests/helpers/chart";
import {
    createBasicChart,
    createGaugeChart,
    createScorecardChart,
} from "@spreadsheet/../tests/helpers/commands";
import { manuallyDispatchProgrammaticEvent } from "@odoo/hoot-dom";

defineDocumentSpreadsheetModels();
describe.current.tags("desktop");

let target;
let serverData;
const chartId = "uuid1";

const inputSelector = "input.o-autocomplete--input";

/** Open the chart side panel of the first chart found in the page*/
async function openChartSidePanel() {
    await contains(".o-chart-container").click({ button: 2 });
    await contains(".o-menu-item[title='Edit']").click();
}

beforeEach(() => {
    target = getFixture();
    serverData = /** @type any */ ({});
    serverData.menus = {
        root: {
            id: "root",
            name: "root",
            appID: "root",
            children: [
                {
                    id: 3,
                    name: "MyApp",
                    xmlid: "documents_spreadsheet.test.app",
                    appID: 3,
                    actionID: "menuAction",
                    children: [
                        {
                            id: 1,
                            name: "test menu 1",
                            xmlid: "documents_spreadsheet.test.menu",
                            appID: 3,
                            actionID: "menuAction",
                        },
                        {
                            id: 2,
                            name: "test menu 2",
                            xmlid: "documents_spreadsheet.test.menu2",
                            appID: 3,
                            actionID: "menuAction2",
                        },
                    ],
                },
            ],
        },
    };
    serverData.actions = {
        menuAction: {
            id: 99,
            xml_id: "ir.ui.menu",
            name: "menuAction",
            res_model: "ir.ui.menu",
            type: "ir.actions.act_window",
            views: [[false, "list"]],
        },
        menuAction2: {
            id: 100,
            xml_id: "ir.ui.menu",
            name: "menuAction2",
            res_model: "ir.ui.menu",
            type: "ir.actions.act_window",
            views: [[false, "list"]],
        },
    };
    serverData.views = {};
    serverData.models = {
        ...getBasicData(),
        "ir.ui.menu": {
            records: [
                {
                    id: 1,
                    name: "test menu 1",
                    action: "action1",
                    group_ids: [10],
                },
                {
                    id: 2,
                    name: "test menu 2",
                    action: "action2",
                    group_ids: [10],
                },
            ],
        },
        "res.users": {
            records: [
                {
                    id: 1,
                    name: "Raoul",
                    group_ids: [10],
                    partner_id: serverState.partnerId,
                    active: true,
                },
                { id: serverState.odoobotId, name: "OdooBot" },
            ],
        },
        "ir.actions": {
            records: [{ id: 1 }],
        },
        "res.group": {
            records: [{ id: 10, name: "test group" }],
        },
    };
    serverState.userId = 1;
});

describe("Link Menus", () => {
    test("can link an odoo menu to a basic chart chart in the side panel", async function () {
        const { model } = await createSpreadsheet({ serverData });
        createBasicChart(model, chartId);
        await animationFrame();
        await openChartSidePanel();
        let odooLink = model.getters.getChartOdooLink(chartId);
        expect(odooLink).toBe(undefined, { message: "No menu linked with chart at start" });

        expect(".o-ir-menu-selector input").toHaveCount(1, {
            message: "A menu to link charts to odoo menus was added to the side panel",
        });
        await contains(".o-ir-menu-selector input").click();
        await contains(".ui-menu-item").click();
        odooLink = model.getters.getChartOdooLink(chartId);
        expect(odooLink.odooMenuId).toBe("documents_spreadsheet.test.menu", {
            message: "Odoo menu is linked to chart",
        });
    });

    test("can link an odoo menu to a scorecard chart chart in the side panel", async function () {
        const { model } = await createSpreadsheet({ serverData });
        createScorecardChart(model, chartId);
        await animationFrame();
        await openChartSidePanel();
        let odooLink = model.getters.getChartOdooLink(chartId);
        expect(odooLink).toBe(undefined, { message: "No menu linked with chart at start" });

        expect(".o-ir-menu-selector input").toHaveCount(1, {
            message: "A menu to link charts to odoo menus was added to the side panel",
        });
        await contains(".o-ir-menu-selector input").click();
        await contains(".ui-menu-item").click();
        odooLink = model.getters.getChartOdooLink(chartId);
        expect(odooLink.odooMenuId).toBe("documents_spreadsheet.test.menu", {
            message: "Odoo menu is linked to chart",
        });
    });

    test("can link an odoo menu to a gauge chart chart in the side panel", async function () {
        const { model } = await createSpreadsheet({ serverData });
        createGaugeChart(model, chartId);
        await animationFrame();
        await openChartSidePanel();
        let odooLink = model.getters.getChartOdooLink(chartId);
        expect(odooLink).toBe(undefined, { message: "No menu linked with chart at start" });

        const irMenuField = target.querySelector(".o-ir-menu-selector input");
        expect(".o-ir-menu-selector input").toHaveCount(1, {
            message: "A menu to link charts to odoo menus was added to the side panel",
        });
        await contains(irMenuField).click();
        await contains(".ui-menu-item").click();
        odooLink = model.getters.getChartOdooLink(chartId);
        expect(odooLink.odooMenuId).toBe("documents_spreadsheet.test.menu", {
            message: "Odoo menu is linked to chart",
        });
    });

    test("can remove link between an odoo menu and a chart in the side panel", async function () {
        const { model } = await createSpreadsheet({ serverData });
        createBasicChart(model, chartId);
        await animationFrame();
        model.dispatch("UPDATE_ODOO_LINK_TO_CHART", {
            chartId,
            odooLink: { type: "odooMenu", odooMenuId: "documents_spreadsheet.test.menu" },
        });
        let odooLink = model.getters.getChartOdooLink(chartId);
        expect(odooLink).not.toBe(undefined, {
            message: "There is menu linked with chart at start",
        });
        await openChartSidePanel();
        await animationFrame();
        const irMenuField = target.querySelector(".o-ir-menu-selector input");

        // edit() helper is not working on Many2XAutocomplete for whatever reason
        irMenuField.value = "";
        await manuallyDispatchProgrammaticEvent(irMenuField, "change");

        await animationFrame();
        odooLink = model.getters.getChartOdooLink(chartId);
        expect(odooLink).toBe(undefined, { message: "no menu is linked to chart" });
    });

    test("Linked menu change in the side panel when we select another chart", async function () {
        const { model } = await createSpreadsheet({ serverData });
        const chartId2 = "id2";
        createBasicChart(model, chartId);
        createBasicChart(model, chartId2);
        await animationFrame();
        model.dispatch("UPDATE_ODOO_LINK_TO_CHART", {
            chartId,
            odooLink: { type: "odooMenu", odooMenuId: 1 },
        });
        model.dispatch("UPDATE_ODOO_LINK_TO_CHART", {
            chartId: chartId2,
            odooLink: { type: "odooMenu", odooMenuId: 2 },
        });
        await openChartSidePanel();
        await animationFrame();

        let irMenuInput = target.querySelector(".o-ir-menu-selector input");
        expect(irMenuInput).toHaveValue("MyApp/test menu 1");

        const figure2 = target.querySelectorAll(".o-figure")[1];
        await contains(figure2).click();
        irMenuInput = target.querySelector(".o-ir-menu-selector input");
        expect(irMenuInput).toHaveValue("MyApp/test menu 2");
    });
});

describe("Link Datasources", () => {
    test("Datasource link is invisible if no datatourse loaded", async function () {
        const { model } = await createSpreadsheet({ serverData });
        createBasicChart(model, chartId);
        await animationFrame();
        await openChartSidePanel();
        expect("select.datasource-link").toHaveCount(0);
    });

    test("can link an odoo datasource to a basic chart chart in the side panel", async function () {
        const { model, pivotId } = await createSpreadsheetWithPivot({ serverData });
        await mountSpreadsheet(model);
        createBasicChart(model, chartId);
        await animationFrame();
        await openChartSidePanel();
        let dataSourceLink = model.getters.getChartOdooLink(chartId);
        expect(dataSourceLink).toBe(undefined, { message: "No menu linked with chart at start" });

        await contains(".o-radio input[value='dataSource']").click();
        expect(inputSelector).toHaveCount(1, {
            message: "Datasource selector is present",
        });
        await contains(inputSelector).click();
        await contains(".o-autocomplete--dropdown-item:first").click();
        dataSourceLink = model.getters.getChartOdooLink(chartId);
        expect(dataSourceLink).toEqual(
            { type: "dataSource", dataSourceCoreId: pivotId, dataSourceType: "pivot" },
            {
                message: "DataSource is linked to chart",
            }
        );
    });

    test("can link an odoo datasource to a scorecard chart chart in the side panel", async function () {
        const { model, pivotId } = await createSpreadsheetWithPivot({ serverData });
        await mountSpreadsheet(model);
        createScorecardChart(model, chartId);
        await animationFrame();
        await openChartSidePanel();
        let dataSourceLink = model.getters.getChartOdooLink(chartId);
        expect(dataSourceLink).toBe(undefined, { message: "No menu linked with chart at start" });

        await contains(".o-radio input[value='dataSource']").click();
        expect(inputSelector).toHaveCount(1, {
            message: "Datasource selector is present",
        });
        await contains(inputSelector).click();
        await contains(".o-autocomplete--dropdown-item:first").click();
        dataSourceLink = model.getters.getChartOdooLink(chartId);
        expect(dataSourceLink).toEqual(
            { type: "dataSource", dataSourceCoreId: pivotId, dataSourceType: "pivot" },
            {
                message: "DataSource is linked to chart",
            }
        );
    });

    test("can link an odoo datasource to a gauge chart chart in the side panel", async function () {
        const { model, pivotId } = await createSpreadsheetWithPivot({ serverData });
        await mountSpreadsheet(model);
        createGaugeChart(model, chartId);
        await animationFrame();
        await openChartSidePanel();
        let dataSourceLink = model.getters.getChartOdooLink(chartId);
        expect(dataSourceLink).toBe(undefined, { message: "No menu linked with chart at start" });

        await contains(".o-radio input[value='dataSource']").click();
        expect(inputSelector).toHaveCount(1, {
            message: "Datasource selector is present",
        });
        await contains(inputSelector).click();
        await contains(".o-autocomplete--dropdown-item:first").click();
        dataSourceLink = model.getters.getChartOdooLink(chartId);
        expect(dataSourceLink).toEqual(
            { type: "dataSource", dataSourceCoreId: pivotId, dataSourceType: "pivot" },
            {
                message: "DataSource is linked to chart",
            }
        );
    });

    test("can remove link between an odoo datasource and a chart in the side panel", async function () {
        const { model, pivotId } = await createSpreadsheetWithPivot({ serverData });
        await mountSpreadsheet(model);
        createBasicChart(model, chartId);
        model.dispatch("UPDATE_ODOO_LINK_TO_CHART", {
            chartId,
            odooLink: { type: "dataSource", dataSourceCoreId: pivotId, dataSourceType: "pivot" },
        });
        await animationFrame();
        await openChartSidePanel();
        let dataSourceLink = model.getters.getChartOdooLink(chartId);
        expect(dataSourceLink).toEqual(
            { type: "dataSource", dataSourceCoreId: pivotId, dataSourceType: "pivot" },
            { message: "No menu linked with chart at start" }
        );
        expect(inputSelector).toHaveCount(1, {
            message: "Datasource selector is present",
        });

        await contains(inputSelector).click();
        await contains(inputSelector).clear({ confirm: "blur" });

        dataSourceLink = model.getters.getChartOdooLink(chartId);
        expect(dataSourceLink).toBe(undefined, {
            message: "No dataSource is linked to chart",
        });
    });

    test("Linked datasource change in the side panel when we select another chart", async function () {
        const { model } = await createSpreadsheetWithPivotAndList({ serverData });
        const listId = model.getters.getListIds()[0];
        const pivotId = model.getters.getPivotIds()[0];
        const chartId2 = "id2";
        createBasicChart(model, chartId);
        createBasicChart(model, chartId2);
        await mountSpreadsheet(model);

        model.dispatch("UPDATE_ODOO_LINK_TO_CHART", {
            chartId,
            odooLink: { type: "dataSource", dataSourceCoreId: pivotId, dataSourceType: "pivot" },
        });
        model.dispatch("UPDATE_ODOO_LINK_TO_CHART", {
            chartId: chartId2,
            odooLink: { type: "dataSource", dataSourceCoreId: listId, dataSourceType: "list" },
        });
        await openChartSidePanel();
        await animationFrame();
        await contains(".o-radio input[value='dataSource']").click();
        let linkDsInput = target.querySelector(inputSelector);
        expect(linkDsInput.value).toBe("Pivot #1 - Partner Pivot");

        const figure2 = target.querySelectorAll(".o-figure")[1];
        await contains(figure2).click();
        linkDsInput = target.querySelector(inputSelector);
        expect(linkDsInput.value).toBe("List #1 - List");
    });

    test("radio select disappears when the datasources are removed", async function () {
        const { model } = await createSpreadsheetWithPivotAndList({ serverData });
        const pivotId = model.getters.getPivotIds()[0];
        const listId = model.getters.getListIds()[0];
        createBasicChart(model, chartId);
        await mountSpreadsheet(model);
        await openChartSidePanel();
        await contains(".o-radio input[value='dataSource']").click();

        await contains(inputSelector).click();
        expect(target.querySelectorAll(".o-autocomplete--dropdown-item")).toHaveCount(2);
        model.dispatch("REMOVE_PIVOT", { pivotId });
        await animationFrame();
        // close the dropdown
        await contains(inputSelector).click();

        await contains(inputSelector).click();
        expect(target.querySelectorAll(".o-autocomplete--dropdown-item")).toHaveCount(1);
        model.dispatch("REMOVE_ODOO_LIST", { listId });
        await animationFrame();
        expect(".o-radio input[value='dataSource']").toHaveCount(0);
    });

    test("Autocomplete values are properly formatted", async function () {
        const { model } = await createSpreadsheetWithPivotAndList({ serverData });
        createBasicChart(model, chartId);
        insertChartInSpreadsheet(model);
        await mountSpreadsheet(model);
        await openChartSidePanel();
        await contains(".o-radio input[value='dataSource']").click();

        await contains(inputSelector).click();
        const options = target.querySelectorAll(".o-autocomplete--dropdown-item");
        expect([...options].map((node) => node.textContent)).toEqual([
            "Pivot #1 - Partner Pivot",
            "List #1 - List",
            "Chart #1 - Partners",
        ]);
    });

    test("Can jump to linked pivot configuration from chart panel", async () => {
        const { model } = await createSpreadsheetWithPivot({ serverData });
        createBasicChart(model, chartId);
        await mountSpreadsheet(model);
        await openChartSidePanel();
        await contains(".o-radio input[value='dataSource']").click();
        await contains(inputSelector).click();
        await contains(".o-autocomplete--dropdown-item:first").click();
        await contains("i[data-icon='east']").click();
        const target = getFixture();
        const title = target.querySelector(".o-sidePanelTitle").innerText;
        expect(title).toBe("Pivot #1");
    });

    test("Can jump to linked list configuration from chart panel", async () => {
        const { model } = await createSpreadsheetWithList({ serverData });
        createBasicChart(model, chartId);
        await mountSpreadsheet(model);
        await openChartSidePanel();
        await contains(".o-radio input[value='dataSource']").click();
        await contains(inputSelector).click();
        await contains(".o-autocomplete--dropdown-item:first").click();
        await contains("i[data-icon='east']").click();
        const target = getFixture();
        const title = target.querySelector(".o-sidePanelTitle").innerText;
        expect(title).toBe("List #1");
    });

    test("Can jump to linked Odoo chart configuration from chart panel", async () => {
        const { model } = await createSpreadsheetWithList({ serverData });
        createBasicChart(model, chartId);
        await mountSpreadsheet(model);
        await openChartSidePanel();
        await contains(".o-radio input[value='dataSource']").click();
        await contains(inputSelector).click();
        await contains(".o-autocomplete--dropdown-item:first").click();
        await contains("i[data-icon='east']").click();
        const target = getFixture();
        expect(target.querySelector(".o_domain_selector")).not.toBe(undefined);
        expect(target.querySelector(".o_pivot_last_update")).not.toBe(undefined);
    });

    test("Can select different datasources of the same type", async () => {
        const { model, pivotId } = await createSpreadsheetWithPivot({ serverData });
        const newPivotId = "pivot2";
        model.dispatch("DUPLICATE_PIVOT", { pivotId, newPivotId });
        await mountSpreadsheet(model);
        createBasicChart(model, chartId);
        await animationFrame();
        await openChartSidePanel();
        let dataSourceLink = model.getters.getChartOdooLink(chartId);
        expect(dataSourceLink).toBe(undefined, { message: "No menu linked with chart at start" });

        await contains(".o-radio input[value='dataSource']").click();
        expect(inputSelector).toHaveCount(1, {
            message: "Datasource selector is present",
        });
        await contains(inputSelector).click();
        await contains(".o-autocomplete--dropdown-item:first").click();
        expect(inputSelector).toHaveValue("Pivot #1 - Partner Pivot");
        dataSourceLink = model.getters.getChartOdooLink(chartId);
        expect(dataSourceLink).toEqual(
            { type: "dataSource", dataSourceCoreId: pivotId, dataSourceType: "pivot" },
            {
                message: "DataSource is linked to chart",
            }
        );
        await contains(inputSelector).click();
        await contains(".o-autocomplete--dropdown-item:last").click();
        expect(inputSelector).toHaveValue("Pivot #2 - Partner Pivot (copy)");
        dataSourceLink = model.getters.getChartOdooLink(chartId);
        expect(dataSourceLink).toEqual(
            { type: "dataSource", dataSourceCoreId: newPivotId, dataSourceType: "pivot" },
            {
                message: "DataSource is linked to chart",
            }
        );
    });
});
