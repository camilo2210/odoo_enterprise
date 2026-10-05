import {
    defineDocumentSpreadsheetModels,
    defineDocumentSpreadsheetTestAction,
    getBasicData,
    getBasicServerData,
    getDocumentBasicData,
} from "@documents_spreadsheet/../tests/helpers/data";
import {
    createSpreadsheetFromListView,
    invokeInsertListInSpreadsheetDialog,
    spawnListViewForSpreadsheet,
} from "@documents_spreadsheet/../tests/helpers/list_helpers";
import { createSpreadsheet } from "@documents_spreadsheet/../tests/helpers/spreadsheet_test_utils";
import { getHighlightsFromStore } from "@documents_spreadsheet/../tests/helpers/store_helpers";
import { SpreadsheetAction } from "@documents_spreadsheet/bundle/actions/spreadsheet_action";
import { describe, expect, getFixture, test } from "@odoo/hoot";
import { hover, leave } from "@odoo/hoot-dom";
import { animationFrame, mockDate } from "@odoo/hoot-mock";
import * as spreadsheet from "@odoo/o-spreadsheet";
import { onMounted } from "@odoo/owl";
import {
    addGlobalFilter,
    createSheet,
    deleteSheet,
    selectCell,
    setCellContent,
} from "@spreadsheet/../tests/helpers/commands";
import { Partner, Product, ResUsers } from "@spreadsheet/../tests/helpers/data";
import {
    getCellFormula,
    getCellValue,
    getEvaluatedCell,
} from "@spreadsheet/../tests/helpers/getters";
import { insertListInSpreadsheet } from "@spreadsheet/../tests/helpers/list";
import { getZoneOfInsertedDataSource } from "@spreadsheet/../tests/helpers/pivot";
import { doMenuAction, getActionMenu } from "@spreadsheet/../tests/helpers/ui";
import { waitForDataLoaded } from "@spreadsheet/helpers/model";
import {
    getSpreadsheetActionModel,
    editSelectComponent,
} from "@spreadsheet_edition/../tests/helpers/webclient_helpers";
import { InsertListSpreadsheetMenu } from "@spreadsheet_edition/assets/list_view/insert_list_spreadsheet_menu_owl";
import { SpreadsheetSelectorDialog } from "@spreadsheet_edition/assets/components/spreadsheet_selector_dialog/spreadsheet_selector_dialog";
import { insertList } from "@spreadsheet_edition/bundle/list/list_init_callback";
import * as dsHelpers from "@web/../tests/core/tree_editor/condition_tree_editor_test_helpers";
import {
    contains,
    fields,
    getService,
    mountView,
    onRpc,
    pagerNext,
    patchWithCleanup,
    toggleActionMenu,
    makeServerError,
    serverState,
    mockService,
} from "@web/../tests/web_test_helpers";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { mockActionService } from "../helpers/spreadsheet_test_utils";

defineDocumentSpreadsheetModels();
defineDocumentSpreadsheetTestAction();
describe.current.tags("desktop");

const { topbarMenuRegistry, cellMenuRegistry } = spreadsheet.registries;
const { toZone, sanitizeSheetName } = spreadsheet.helpers;

test("insert list formulas", async () => {
    const { model } = await createSpreadsheetFromListView({
        linesNumber: 3,
        serverData: {
            models: getBasicData(),
            views: {
                "partner,false,list": `
                        <list>
                            <field name="foo"/>
                            <field name="bar"/>
                        </list>`,
            },
        },
    });
    expect(model.getters.getListDefinition("1").columns).toMatchObject([
        { name: "foo" },
        { name: "bar" },
    ]);
    expect(getCellFormula(model, "A1")).toBe('=ODOO.LIST.HEADER(1,"foo","Foo")');
    expect(getCellFormula(model, "B1")).toBe('=ODOO.LIST.HEADER(1,"bar","Bar")');
    expect(getCellFormula(model, "A2")).toBe('=ODOO.LIST.VALUE(1,1,"foo")');
    expect(getCellFormula(model, "A3")).toBe('=ODOO.LIST.VALUE(1,2,"foo")');
    expect(getCellFormula(model, "A4")).toBe('=ODOO.LIST.VALUE(1,3,"foo")');
    expect(getCellFormula(model, "A5")).toBe("");
    expect(getCellFormula(model, "B2")).toBe('=ODOO.LIST.VALUE(1,1,"bar")');
    expect(getCellFormula(model, "B3")).toBe('=ODOO.LIST.VALUE(1,2,"bar")');
    expect(getCellFormula(model, "B4")).toBe('=ODOO.LIST.VALUE(1,3,"bar")');
    expect(getCellFormula(model, "B5")).toBe("");
});

test("List export with a invisible field", async () => {
    const { model } = await createSpreadsheetFromListView({
        serverData: {
            models: getBasicData(),
            views: {
                "partner,false,list": `
                        <list string="Partners">
                            <field name="foo" column_invisible="1"/>
                            <field name="bar"/>
                        </list>`,
            },
        },
    });
    expect(model.getters.getListDefinition("1").columns).toEqual([{ name: "bar", string: "Bar" }]);
});

test("List export with a widget handle", async () => {
    const { model } = await createSpreadsheetFromListView({
        serverData: {
            models: getBasicData(),
            views: {
                "partner,false,list": `
                            <list string="Partners">
                                <field name="foo" widget="handle"/>
                                <field name="bar"/>
                            </list>`,
            },
        },
    });
    expect(model.getters.getListDefinition("1").columns).toMatchObject([
        { name: "bar", string: "Bar" },
    ]);
});

test("Lists are inserted with a table in the webclient", async () => {
    const { model } = await createSpreadsheetFromListView();
    const sheetId = model.getters.getActiveSheetId();
    const table = model.getters.getTable({ sheetId, col: 2, row: 2 });
    expect(table.range.zone).toEqual(toZone("A1:D11"));
});

test("property fields are exported", async () => {
    const data = getBasicData();
    const propertyDefinition = {
        type: "char",
        name: "property_char",
        string: "Property char",
    };
    const product = Product._records[0];
    product.properties_definitions = [propertyDefinition];
    data.partner.records = [
        {
            id: 1,
            bar: true,
            product_id: product.id,
            partner_properties: {
                [propertyDefinition.name]: "CHAR",
            },
        },
    ];
    const propertyField = fields.Properties({
        string: "Property char",
        definition_record: "product_id",
        definition_record_field: "properties_definitions",
    });
    Partner._fields.partner_properties = propertyField;
    const { model } = await createSpreadsheetFromListView({
        actions: async () => {
            // display the property which is an optional column
            await contains(".o_optional_columns_dropdown_toggle").click();
            await contains(".o-dropdown--menu input[type='checkbox']").click();
            expect(".o_list_renderer th[data-name='partner_properties.property_char']").toHaveCount(
                1
            );
            expect.step("display_property");
        },
        serverData: {
            models: data,
            views: {
                "partner,false,list": /*xml*/ `
                        <list>
                            <field name="product_id"/>
                            <field name="bar"/>
                            <field name="partner_properties"/>
                        </list>`,
            },
        },
    });
    expect(model.getters.getListDefinition("1").columns).toMatchObject([
        { name: "product_id", string: "Product" },
        { name: "bar", string: "Bar" },
        { name: "partner_properties.property_char", string: "Property char" },
    ]);
    expect.verifySteps(["display_property"]);
});

test("json fields are not exported", async () => {
    const { model } = await createSpreadsheetFromListView({
        serverData: {
            models: getBasicData(),
            views: {
                "partner,false,list": `
                        <list string="Partners">
                            <field name="jsonField"/>
                            <field name="bar"/>
                        </list>`,
            },
        },
    });
    expect(model.getters.getListDefinition("1").columns).toMatchObject([
        { name: "bar", string: "Bar" },
    ]);
});

test("list side panel is open at insertion", async function () {
    await createSpreadsheetFromListView();
    expect(".o-listing-details-side-panel").toHaveCount(1);
});

test("An error is displayed in the side panel if the list has invalid model", async function () {
    const { model, env } = await createSpreadsheetFromListView({
        mockRPC: async function (route, { model, method, kwargs }) {
            if (model === "unknown" && method === "fields_get") {
                throw makeServerError({ code: 404 });
            }
        },
    });
    await contains(".o-sidePanelClose").click();
    const listId = model.getters.getListIds()[0];
    const listDefinition = model.getters.getListDefinition(listId);
    model.dispatch("UPDATE_ODOO_LIST", {
        listId,
        list: {
            ...listDefinition,
            model: "unknown",
        },
    });
    env.openSidePanel("LIST_PROPERTIES_PANEL", { listId });
    await animationFrame();

    expect(".o-validation-error").toHaveCount(1);
});

test("Open list properties", async function () {
    const { env } = await createSpreadsheetFromListView();

    await doMenuAction(topbarMenuRegistry, ["data", "list_data_sources", "item_list_1"], env);
    await animationFrame();
    const target = getFixture();
    const title = target.querySelector(".o-sidePanelTitle").innerText;
    expect(title).toBe("List #1");

    const sections = target.querySelectorAll(".o-section");
    expect(sections.length).toBe(7, { message: "it should have 7 sections" });
    const [listName, listModel, columns, sort, domain, ,] = sections;

    expect(listName.children[0]).toHaveText("List Name");
    expect(listName.querySelector("input").value).toBe("Partners");

    expect(listModel.children[0]).toHaveText("Model");
    expect(listModel.children[1]).toHaveText("Partner (partner)");

    expect(columns.querySelector(".o-section-title > div").firstChild.textContent.trim()).toBe(
        "Columns"
    );
    expect(sort.querySelector(".o-section-title > div").firstChild.textContent.trim()).toBe(
        "Sorting"
    );

    expect(domain.children[0]).toHaveText("Domain");
    expect(domain.children[1]).toHaveText("Match all records\nInclude archived");
});

test("A warning is displayed in the side panel if the list is unused", async function () {
    const { model, env } = await createSpreadsheetFromListView();

    const [listId] = model.getters.getListIds();
    env.openSidePanel("LIST_PROPERTIES_PANEL", { listId });
    await animationFrame();

    expect(".o-validation-warning").toHaveCount(0);

    createSheet(model, { sheetId: "sh2", name: "Sheet2" });
    const activeSheetId = model.getters.getActiveSheetId();
    model.dispatch("ACTIVATE_SHEET", { sheetIdFrom: activeSheetId, sheetIdTo: "sh2" });
    deleteSheet(model, activeSheetId);
    await animationFrame();

    expect(".o-validation-warning").toHaveCount(1);

    model.dispatch("REQUEST_UNDO");
    await animationFrame();
    expect(".o-validation-warning").toHaveCount(0);
});

test("Deleting the list closes the side panel", async function () {
    const { model, env } = await createSpreadsheetFromListView();
    const [listId] = model.getters.getListIds();
    env.openSidePanel("LIST_PROPERTIES_PANEL", { listId });
    await animationFrame();
    const titleSelector = ".o-sidePanelTitle";
    expect(titleSelector).toHaveText("List #1");

    model.dispatch("REMOVE_ODOO_LIST", { listId });
    await animationFrame();
    expect(titleSelector).toHaveCount(0);
});

test("Undo a list insertion closes the side panel", async function () {
    const { model, env } = await createSpreadsheetFromListView();
    const [listId] = model.getters.getListIds();
    env.openSidePanel("LIST_PROPERTIES_PANEL", { listId });
    await animationFrame();
    const titleSelector = ".o-sidePanelTitle";
    expect(titleSelector).toHaveText("List #1");

    model.dispatch("REQUEST_UNDO");
    model.dispatch("REQUEST_UNDO");
    await animationFrame();
    expect(titleSelector).toHaveCount(0);
});

test("Add list in an existing spreadsheet", async () => {
    const { model, env } = await createSpreadsheetFromListView();
    const list = model.getters.getListDefinition("1");
    const callback = insertList.bind({ isEmptySpreadsheet: false })({
        list: {
            ...list,
            columns: list.columns,
        },
        threshold: 10,
        name: "my list",
    });
    createSheet(model, { sheetId: "42", position: 1 });
    const activeSheetId = model.getters.getActiveSheetId();
    expect(model.getters.getSheetIds()).toEqual([activeSheetId, "42"]);
    await callback(model, env.__spreadsheet_stores__);
    expect(model.getters.getSheetIds().length).toBe(3);
    expect(model.getters.getSheetIds()[0]).toEqual(activeSheetId);
    expect(model.getters.getSheetIds()[1]).toBe("42");
    expect(".o-listing-details-side-panel").toHaveCount(1);
});

test("Verify absence of list properties and sorting list on non-list cell", async function () {
    const { model, env } = await createSpreadsheetFromListView();
    selectCell(model, "Z26");
    const propertiesItem = cellMenuRegistry
        .getAll()
        .find((item) => item.id === "listing_properties");
    const sortingItem = cellMenuRegistry.getAll().find((item) => item.id === "sorting_list");
    expect(propertiesItem.isVisible(env)).toBe(false);
    expect(sortingItem.isVisible(env)).toBe(false);
});

test("Verify absence of list properties and sorting list on formula with invalid list Id", async function () {
    const { model, env } = await createSpreadsheetFromListView();
    setCellContent(model, "A1", `=ODOO.LIST.HEADER("fakeId", "foo")`);
    const propertiesItem = cellMenuRegistry
        .getAll()
        .find((item) => item.id === "listing_properties");
    const sortingItem = cellMenuRegistry.getAll().find((item) => item.id === "sorting_list");
    expect(propertiesItem.isVisible(env)).toBe(false);
    expect(sortingItem.isVisible(env)).toBe(false);
    setCellContent(model, "A1", `=ODOO.LIST.VALUE("fakeId", "2", "bar")`);
    expect(propertiesItem.isVisible(env)).toBe(false);
    expect(sortingItem.isVisible(env)).toBe(false);
});

test("Verify absence of sorting list on static list", async function () {
    const { model, env } = await createSpreadsheetFromListView();
    const sortingItem = cellMenuRegistry.getAll().find((item) => item.id === "sorting_list");
    selectCell(model, "A1");
    expect(sortingItem.isVisible(env)).toBe(false);
});

test("Verify presence of sorting list on dynamic list", async function () {
    const { model, env } = await createSpreadsheetFromListView();
    const sortingItem = cellMenuRegistry.getAll().find((item) => item.id === "sorting_list");
    setCellContent(model, "G1", `=ODOO.LIST(1)`);
    selectCell(model, "G1");
    expect(sortingItem.isVisible(env)).toBe(true);
});

test("Re-insert a list correctly ask for lines number", async function () {
    const { model, env } = await createSpreadsheetFromListView();
    selectCell(model, "Z26");
    await doMenuAction(
        topbarMenuRegistry,
        ["data", "reinsert_static_list", "reinsert_static_list_1"],
        env
    );
    await animationFrame();
    expect(".modal-body input").toHaveCount(1);
    expect(".modal-body input").toHaveProperty("type", "number");

    await contains(".o_dialog .btn-secondary").click(); // cancel
    expect(getCellFormula(model, "Z26")).toBe("", { message: "the list is not re-inserted" });

    await doMenuAction(
        topbarMenuRegistry,
        ["data", "reinsert_static_list", "reinsert_static_list_1"],
        env
    );
    await animationFrame();
    await contains(".o_dialog .btn-primary").click(); // confirm
    expect(getCellFormula(model, "Z26")).toBe('=ODOO.LIST.HEADER(1,"foo","Foo")', {
        message: "the list is re-inserted",
    });
});

test("Re-insert a static list keeps stored header definitions", async function () {
    const { model, env } = await createSpreadsheetFromListView();
    const listId = model.getters.getListIds()[0];
    const list = model.getters.getListDefinition(listId);

    model.dispatch("UPDATE_ODOO_LIST", {
        listId,
        list: {
            ...list,
            columns: [
                { name: "foo" },
                { name: "bar", string: "Fixed Bar" },
                { name: "date", string: "Custom Date" },
            ],
        },
    });

    selectCell(model, "Z26");

    await doMenuAction(
        topbarMenuRegistry,
        ["data", "reinsert_static_list", "reinsert_static_list_1"],
        env
    );
    await animationFrame();

    await contains(".modal-body input").edit("10");
    await contains(".modal-content > .modal-footer > .btn-primary").click();

    expect(getCellFormula(model, "Z26")).toBe('=ODOO.LIST.HEADER(1,"foo")');
    expect(getCellFormula(model, "AA26")).toBe('=ODOO.LIST.HEADER(1,"bar","Fixed Bar")');
    expect(getCellFormula(model, "AB26")).toBe('=ODOO.LIST.HEADER(1,"date","Custom Date")');
});

test("Validates input and shows error message when input is invalid", async function () {
    const { model, env } = await createSpreadsheetFromListView();
    selectCell(model, "Z1");

    await doMenuAction(
        topbarMenuRegistry,
        ["data", "reinsert_static_list", "reinsert_static_list_1"],
        env
    );
    await animationFrame();

    await contains(".modal-body input").edit("");
    await contains(".modal-content > .modal-footer > .btn-primary").click();

    expect(".modal-body span.text-danger:only").toHaveText("Please enter a valid number.");
});

test("Re-insert a static list with a selected number of records", async function () {
    const { model, env } = await createSpreadsheetFromListView();
    selectCell(model, "Z1");

    await doMenuAction(
        topbarMenuRegistry,
        ["data", "reinsert_static_list", "reinsert_static_list_1"],
        env
    );
    await animationFrame();

    await contains(".modal-body input").edit("2000");
    await contains(".modal-content > .modal-footer > .btn-primary").click();

    expect(model.getters.getNumberRows(model.getters.getActiveSheetId())).toBe(2001);
    expect(getCellFormula(model, "Z2001")).toBe('=ODOO.LIST.VALUE(1,2000,"foo")');
});

test("Re-insert a dynamic list with a selected number of records", async function () {
    const { model, env } = await createSpreadsheetFromListView();
    selectCell(model, "Z1");

    await doMenuAction(
        topbarMenuRegistry,
        ["data", "reinsert_dynamic_list", "reinsert_dynamic_list_1"],
        env
    );
    await animationFrame();

    await contains(".modal-body input").edit("2000");
    await contains(".modal-content > .modal-footer > .btn-primary").click();

    expect(model.getters.getNumberRows(model.getters.getActiveSheetId())).toBe(2001);
    expect(getCellFormula(model, "Z1")).toBe("=ODOO.LIST(1,2000)");
});

test("Re-insert a static list also applies a table", async function () {
    const { model, env } = await createSpreadsheetFromListView();
    const sheetId = model.getters.getActiveSheetId();
    let table = model.getters.getTable({ sheetId, col: 0, row: 49 });
    expect(table).toBe(undefined);

    selectCell(model, "A50");

    await doMenuAction(
        topbarMenuRegistry,
        ["data", "reinsert_static_list", "reinsert_static_list_1"],
        env
    );
    await animationFrame();

    await contains(".modal-body input").edit("10");
    await contains(".modal-content > .modal-footer > .btn-primary").click();

    table = model.getters.getTable({ sheetId, col: 0, row: 49 });
    expect(table.range.zone).toEqual(toZone("A50:D60"));
});

test("Re-insert a dynamic list also applies a table", async function () {
    const { model, env } = await createSpreadsheetFromListView();
    const sheetId = model.getters.getActiveSheetId();
    let table = model.getters.getTable({ sheetId, col: 0, row: 49 });
    expect(table).toBe(undefined);

    selectCell(model, "A50");

    await doMenuAction(
        topbarMenuRegistry,
        ["data", "reinsert_dynamic_list", "reinsert_dynamic_list_1"],
        env
    );
    await animationFrame();

    await contains(".modal-body input").edit("10");
    await contains(".modal-content > .modal-footer > .btn-primary").click();

    table = model.getters.getTable({ sheetId, col: 0, row: 49 });
    expect(table.range.zone).toEqual(toZone("A50:D54"));
});

test("user related context is not saved in the spreadsheet", async function () {
    ResUsers._records = getDocumentBasicData().models["res.users"].records;
    registry.category("favoriteMenu").add(
        "insert-in-spreadsheet-menu",
        {
            Component: InsertListSpreadsheetMenu,
            groupNumber: 4,
        },
        { sequence: 5 }
    );

    patchWithCleanup(SpreadsheetSelectorDialog.prototype, {
        setup() {
            super.setup();
            expect(this.props.actionOptions.preProcessingAsyncActionData.list.context).toEqual(
                {
                    default_stage_id: 5,
                },
                { message: "user related context is not stored in context" }
            );
        },
    });
    serverState.companies = [{ id: 15, name: "Hermit" }];

    const userCtx = user.context;
    patchWithCleanup(user, {
        get context() {
            return Object.assign({}, userCtx, {
                allowed_company_ids: [15],
                tz: "bx",
                lang: "FR",
                uid: 4,
            });
        },
    });
    patchWithCleanup(user, { userId: 4 });
    const context = {
        ...user.context,
        default_stage_id: 5,
    };
    const { env } = await mountView({
        type: "list",
        resModel: "partner",
        context,
        arch: `
                <list string="Partners">
                    <field name="bar"/>
                    <field name="product_id"/>
                </list>
            `,
        config: {
            actionType: "ir.actions.act_window",
            getDisplayName: () => "Test",
            viewType: "list",
        },
    });
    await invokeInsertListInSpreadsheetDialog(env);
    await contains(".modal button.btn-primary").click();
});

test("Selected records from current page are inserted correctly", async function () {
    const def = Promise.withResolvers();
    let spreadsheetAction = {};
    patchWithCleanup(SpreadsheetAction.prototype, {
        setup() {
            super.setup();
            onMounted(() => {
                spreadsheetAction = this;
                def.resolve();
            });
        },
    });
    const serverData = {
        models: getBasicData(),
        views: {
            "partner,false,list": `
                    <list limit="2">
                        <field name="foo"/>
                    </list>`,
        },
    };
    await spawnListViewForSpreadsheet({
        serverData,
    });

    /** Insert the selected records from current page in a new spreadsheet */
    const target = getFixture();
    await contains(target.querySelectorAll("td.o_list_record_selector input")[1]).click();
    await pagerNext();
    await contains(target.querySelectorAll("td.o_list_record_selector input")[0]).click();
    await toggleActionMenu();
    const insertMenuItem = [...target.querySelectorAll(".o-dropdown--menu .o_menu_item")].filter(
        (el) => el.innerText === "Insert in spreadsheet"
    )[0];
    await contains(insertMenuItem).click();
    await contains(".modal-content > .modal-footer > .btn-primary").click();

    await def.promise;
    const model = getSpreadsheetActionModel(spreadsheetAction);
    await waitForDataLoaded(model);
    expect(getCellValue(model, "A2")).toBe(17, {
        message: "First record from page 2 (i.e. 3 of 4 records) should be inserted",
    });
    expect(getCellValue(model, "A3")).toBe(null);
});

test("Selected all records from current page are inserted correctly", async function () {
    const def = Promise.withResolvers();
    let spreadsheetAction = {};
    patchWithCleanup(SpreadsheetAction.prototype, {
        setup() {
            super.setup();
            onMounted(() => {
                spreadsheetAction = this;
                def.resolve();
            });
        },
    });
    const serverData = {
        models: getBasicData(),
        views: {
            "partner,false,list": `
                    <list limit="2">
                        <field name="foo"/>
                    </list>`,
        },
    };
    await spawnListViewForSpreadsheet({
        serverData,
    });

    /** Insert the selected records from current page in a new spreadsheet */
    const target = getFixture();
    await contains(target.querySelectorAll("td.o_list_record_selector input")[1]).click();
    await contains(target.querySelectorAll("td.o_list_record_selector input")[0]).click();
    await contains(".o_select_domain").click();
    await toggleActionMenu();
    const insertMenuItem = [...target.querySelectorAll(".o-dropdown--menu .o_menu_item")].filter(
        (el) => el.innerText === "Insert in spreadsheet"
    )[0];
    await contains(insertMenuItem).click();
    await contains(".modal-content > .modal-footer > .btn-primary").click();

    await def.promise;
    const model = getSpreadsheetActionModel(spreadsheetAction);
    await waitForDataLoaded(model);
    expect(getCellValue(model, "A2")).toBe(12, {
        message: "First record from page 2 (i.e. 3 of 4 records) should be inserted",
    });
    expect(getCellValue(model, "A3")).toBe(1);
    expect(getCellValue(model, "A4")).toBe(17);
    expect(getCellValue(model, "A5")).toBe(2);
});

test("Insert in spreadsheet is avaiblable on a list grouped by m2m field", async function () {
    let spreadsheetAction;
    patchWithCleanup(SpreadsheetAction.prototype, {
        setup() {
            super.setup();
            spreadsheetAction = this;
        },
    });
    const serverData = {
        models: getBasicData(),
        views: {
            "partner,false,list": `
                    <list>
                        <field name="foo"/>
                    </list>`,
        },
    };
    await spawnListViewForSpreadsheet({
        serverData,
        groupBy: ["tag_ids"],
    });
    const target = getFixture();
    await contains(target.querySelectorAll(".o_list_record_selector input")[0]).click();
    await toggleActionMenu();
    await contains(".o-dropdown--menu .o_menu_item:has([data-icon='view_list'])").click();
    await contains(".modal button.btn-primary").click();
    await animationFrame();

    const model = getSpreadsheetActionModel(spreadsheetAction);
    await waitForDataLoaded(model);
    expect(getCellValue(model, "A2")).toBe(12);
    expect(getCellValue(model, "A3")).toBe(1);
    expect(getCellValue(model, "A4")).toBe(17);
    expect(getCellValue(model, "A5")).toBe(2);
});

test("Can see record of a list", async function () {
    const { webClient, model } = await createSpreadsheetFromListView();
    const listId = model.getters.getListIds()[0];
    const dataSource = model.getters.getListDataSource(listId);
    const env = {
        ...webClient.env,
        model,
        services: {
            ...model.config.custom.env.services,
            action: {
                doAction: (params) => {
                    expect.step(params.res_model);
                    expect.step(params.res_id.toString());
                },
            },
        },
    };
    selectCell(model, "A2");
    const root = cellMenuRegistry.getAll().find((item) => item.id === "list_see_record");
    await root.execute(env);
    expect.verifySteps(["partner", dataSource.getIdFromPosition(0).toString()]);

    selectCell(model, "A3");
    await root.execute(env);
    expect.verifySteps(["partner", dataSource.getIdFromPosition(1).toString()]);

    // From a cell inside a merge
    model.dispatch("ADD_MERGE", {
        sheetId: model.getters.getActiveSheetId(),
        target: [toZone("A3:B3")],
        force: true, // there are data in B3
    });
    selectCell(model, "B3");
    await root.execute(env);
    expect.verifySteps(["partner", dataSource.getIdFromPosition(1).toString()]);
});

test("See record of list is only displayed on list formula with only one list formula", async function () {
    const { webClient, model } = await createSpreadsheetFromListView();
    const env = {
        ...webClient.env,
        model,
        services: model.config.custom.env.services,
    };
    setCellContent(model, "A1", "test");
    setCellContent(model, "A2", `=ODOO.LIST.VALUE("1","1","foo")`);
    setCellContent(model, "A3", `=ODOO.LIST.VALUE("1","1","foo")+LIST("1","1","foo")`);
    const root = cellMenuRegistry.getAll().find((item) => item.id === "list_see_record");

    selectCell(model, "A1");
    expect(root.isVisible(env)).toBe(false);
    selectCell(model, "A2");
    expect(root.isVisible(env)).toBe(true);
    selectCell(model, "A3");
    expect(root.isVisible(env)).toBe(false);
});

test("See records is visible even if the formula is lowercase", async function () {
    const { env, model } = await createSpreadsheetFromListView();
    selectCell(model, "B2");
    const root = cellMenuRegistry.getAll().find((item) => item.id === "list_see_record");
    expect(root.isVisible(env)).toBe(true);
    setCellContent(model, "B2", getCellFormula(model, "B2").replace("ODOO.LIST", "odoo.list"));
    expect(root.isVisible(env)).toBe(true);
});

test("See records is not visible if the formula is in error", async function () {
    const { env, model } = await createSpreadsheetFromListView();
    selectCell(model, "B2");
    const root = cellMenuRegistry.getAll().find((item) => item.id === "list_see_record");
    expect(root.isVisible(env)).toBe(true);
    setCellContent(
        model,
        "B2",
        getCellFormula(model, "B2").replace(`ODOO.LIST.VALUE(1`, `ODOO.LIST.VALUE("5)`)
    ); //Invalid id
    expect(getEvaluatedCell(model, "B2").message).not.toBe(undefined);
    expect(root.isVisible(env)).toBe(false);
});

test("See record.isVisible() don't throw on spread values", async function () {
    const { env, model } = await createSpreadsheet();
    setCellContent(model, "A1", "A1");
    setCellContent(model, "A2", "A2");
    setCellContent(model, "C1", "=TRANSPOSE(A1:A2)");
    selectCell(model, "D1");
    await animationFrame();
    const root = cellMenuRegistry.getAll().find((item) => item.id === "list_see_record");
    expect(root.isVisible(env)).toBe(false);
});

test("Cannot see record of list formula without value", async function () {
    const { env, model } = await createSpreadsheetFromListView();
    expect(getCellFormula(model, "A6")).toBe(`=ODOO.LIST.VALUE(1,5,"foo")`);
    expect(getCellValue(model, "A6")).toBe("", { message: "A6 is empty" });
    selectCell(model, "A6");
    const action = await getActionMenu(cellMenuRegistry, ["list_see_record"], env);
    expect(action.isVisible(env)).toBe(false);
});

test("'See records' loads a specific action if set in the list definition", async function () {
    const actionXmlId = "spreadsheet.partner_action";
    const { webClient, model } = await createSpreadsheetFromListView({ actionXmlId });
    const actionService = getService("action");
    const env = {
        ...webClient.env,
        model,
        services: {
            ...model.config.custom.env.services,
            action: {
                ...actionService,
                doAction: (params) => {
                    expect(params.id).not.toBe(undefined);
                    expect(params.xml_id).not.toBe(undefined);
                    expect.step(params.res_model);
                    expect.step(params.res_id.toString());
                },
            },
        },
    };
    selectCell(model, "C3");
    await animationFrame();
    const root = cellMenuRegistry.getAll().find((item) => item.id === "list_see_record");
    await root.execute(env);
    expect.verifySteps(["partner", "2"]);
});

test("Context is passed correctly to the action service", async function () {
    const serverData = getBasicServerData();
    const actionXmlId = "spreadsheet.partner_action";
    serverData.views["partner,false,search"] = /* xml */ `
        <search>
            <filter string="Filter" name="filter" context="{'search_default_filter': 1}" />
        </search>
    `;

    const { model, env } = await createSpreadsheetFromListView({
        serverData,
        actionXmlId,
        additionalContext: { search_default_filter: 1 },
    });

    mockActionService((action) => {
        expect.step("loadAction");
        expect(action.context).toEqual({ search_default_filter: 1 });
    });

    selectCell(model, "A2");
    await animationFrame();
    const root = cellMenuRegistry.getAll().find((item) => item.id === "list_see_record");
    await root.execute(env);
    expect.verifySteps(["loadAction"]);
});

test("Update the list title from the side panel", async function () {
    const { model, env } = await createSpreadsheetFromListView();
    const [listId] = model.getters.getListIds();
    env.openSidePanel("LIST_PROPERTIES_PANEL", { listId });
    await animationFrame();
    const target = await contains(".o-sidePanel .os-input");
    await target.click();
    await target.edit("new name");
    expect(model.getters.getListName(listId)).toBe("new name");
});

test("list with a contextual domain", async () => {
    // TODO: the date is coded at 12PM so the test won't fail if the timezone is not UTC. It will still fail on some
    // timezones (GMT +13). The good way to do the test would be to patch the time zone and the date correctly.
    // But PyDate uses new Date() instead of luxon, which cannot be correctly patched.
    mockDate("2016-05-14 12:00:00");
    const serverData = getBasicServerData();
    serverData.models.partner.records = [
        {
            id: 1,
            probability: 0.5,
            date: "2016-05-14",
        },
    ];
    serverData.views["partner,false,search"] = /* xml */ `
            <search>
                <filter string="Filter" name="filter" domain="[('date', '=', context_today())]"/>
            </search>
        `;
    serverData.views["partner,false,list"] = /* xml */ `
            <list>
                <field name="foo"/>
            </list>
        `;
    const { model } = await createSpreadsheetFromListView({
        serverData,
        additionalContext: { search_default_filter: 1 },
        mockRPC: function (route, args) {
            if (args.method === "web_search_read") {
                expect(args.kwargs.domain).toEqual([["date", "=", "2016-05-14"]], {
                    message: "data should be fetched with the evaluated the domain",
                });
                expect.step("web_search_read");
            }
        },
    });
    const listId = "1";
    expect(model.getters.getListDefinition(listId).domain).toEqual(
        '[("date", "=", context_today())]'
    );
    expect(model.exportData().lists[listId].domain).toBe('[("date", "=", context_today())]', {
        message: "domain is exported with the dynamic value",
    });
    expect.verifySteps([
        "web_search_read", // list view is loaded
        "web_search_read", // the data is loaded in the spreadsheet
    ]);
});

test("Update the list domain from the side panel", async function () {
    onRpc("/web/domain/validate", () => true);
    const { model, env } = await createSpreadsheetFromListView();
    const [listId] = model.getters.getListIds();
    env.openSidePanel("LIST_PROPERTIES_PANEL", { listId });
    await animationFrame();
    const fixture = getFixture();
    await contains(".o_edit_domain").click();
    await dsHelpers.addNewRule();
    await contains(".modal-footer .btn-primary").click();
    expect(model.getters.getListDefinition(listId).domain).toEqual([["id", "=", 1]]);
    expect(dsHelpers.getConditionText(fixture)).toBe("Id = 1");
});

test("Update the list sorting from the side panel", async function () {
    const { model, env } = await createSpreadsheetFromListView();
    const [listId] = model.getters.getListIds();
    env.openSidePanel("LIST_PROPERTIES_PANEL", { listId });
    await animationFrame();
    await contains(".add-dimension:eq(1)").click();
    for (let i = 0; i < 5; i++) {
        await contains(".o-popover input").press("ArrowDown");
    }
    await contains(".o-autocomplete-value-focus").click();
    expect(model.getters.getListDefinition(listId).orderBy).toEqual([{ name: "date", asc: true }]);
    await contains(".add-dimension:eq(1)").click();
    for (let i = 0; i < 7; i++) {
        await contains(".o-popover input").press("ArrowDown");
    }
    await contains(".o-autocomplete-value-focus").click();
    await editSelectComponent(".o-select-order:eq(0)", "false");
    expect(".o-select-order:eq(0)").toHaveText("Descending");
    expect(model.getters.getListDefinition(listId).orderBy).toEqual([
        { name: "date", asc: false },
        { name: "foo", asc: true },
    ]);
    model.dispatch("REQUEST_UNDO");
    expect(model.getters.getListDefinition(listId).orderBy).toEqual([
        { name: "date", asc: true },
        { name: "foo", asc: true },
    ]);
    await contains(".o-delete-rule").click();
    expect(model.getters.getListDefinition(listId).orderBy).toEqual([{ name: "foo", asc: true }]);
});

test("List sorting selector should display only sortable fields", async function () {
    Partner._fields.foo = fields.Integer({ sortable: false });
    Partner._fields.bar = fields.Boolean({ sortable: false });
    const { model, env } = await createSpreadsheetFromListView({});
    const [listId] = model.getters.getListIds();
    const fixture = getFixture();
    env.openSidePanel("LIST_PROPERTIES_PANEL", { listId });
    await animationFrame();
    await contains(".add-dimension:eq(1)").click();
    const options = [...fixture.querySelectorAll(".o-popover .o-autocomplete-dropdown > div")];
    const availableFields = options.map((el) => el.innerText);
    expect(availableFields).toEqual([
        "Active",
        "Creation Date",
        "Currency",
        "Date",
        "Display name",
        "field_with_array_agg",
        "Id",
        "Json Field",
        "Last Modified on",
        "Money!",
        "name",
        "Probability",
        "Product",
        "Properties",
        "Tags",
        "Users",
    ]);
});

test("List sorting selector should not display already used fields", async function () {
    Partner._fields.foo = fields.Integer({ sortable: false });
    Partner._fields.bar = fields.Boolean({ sortable: false });
    const { model, env } = await createSpreadsheetFromListView({});
    const [listId] = model.getters.getListIds();
    const fixture = getFixture();
    env.openSidePanel("LIST_PROPERTIES_PANEL", { listId });
    await animationFrame();
    await contains(".add-dimension:eq(1)").click();
    await contains(".o-popover input").press("ArrowDown");
    await contains(".o-popover input").press("ArrowDown");
    await contains(".o-autocomplete-value-focus").click();
    await contains(".add-dimension:eq(1)").click();
    let options = [...fixture.querySelectorAll(".o-popover .o-autocomplete-dropdown > div")];
    let availableFields = options.map((el) => el.innerText);
    expect(availableFields).toEqual([
        "Active",
        /* "Creation Date", this field should not be available anymore as it is used */
        "Currency",
        "Date",
        "Display name",
        "field_with_array_agg",
        "Id",
        "Json Field",
        "Last Modified on",
        "Money!",
        "name",
        "Probability",
        "Product",
        "Properties",
        "Tags",
        "Users",
    ]);
    await contains(".o-popover input").press("ArrowDown");
    await contains(".o-popover input").press("ArrowDown");
    await contains(".o-autocomplete-value-focus").click();
    await contains(".add-dimension:eq(1)").click();
    options = [...fixture.querySelectorAll(".o-popover .o-autocomplete-dropdown > div")];
    availableFields = options.map((el) => el.innerText);
    expect(availableFields).toEqual([
        "Active",
        /* "Creation Date", this field should not be available anymore as it is used */
        /* "Currency", this field should not be available anymore as it is used */
        "Date",
        "Display name",
        "field_with_array_agg",
        "Id",
        "Json Field",
        "Last Modified on",
        "Money!",
        "name",
        "Probability",
        "Product",
        "Properties",
        "Tags",
        "Users",
    ]);
});

test("List sorting selector should display used fields again when corresponding rule is deleted", async function () {
    Partner._fields.foo = fields.Integer({ sortable: false });
    Partner._fields.bar = fields.Boolean({ sortable: false });
    const { model, env } = await createSpreadsheetFromListView({});
    const [listId] = model.getters.getListIds();
    const fixture = getFixture();
    env.openSidePanel("LIST_PROPERTIES_PANEL", { listId });
    await animationFrame();
    await contains(".add-dimension:eq(1)").click();
    await contains(".o-popover input").press("ArrowDown");
    await contains(".o-popover input").press("ArrowDown");
    await contains(".o-autocomplete-value-focus").click();
    await contains(".add-dimension:eq(1)").click();
    let options = [...fixture.querySelectorAll(".o-popover .o-autocomplete-dropdown > div")];
    let availableFields = options.map((el) => el.innerText);
    expect(availableFields).toEqual([
        "Active",
        /* "Creation Date", this field should not be available anymore as it is used */
        "Currency",
        "Date",
        "Display name",
        "field_with_array_agg",
        "Id",
        "Json Field",
        "Last Modified on",
        "Money!",
        "name",
        "Probability",
        "Product",
        "Properties",
        "Tags",
        "Users",
    ]);
    await contains(".o-delete-rule").click();
    await contains(".add-dimension:eq(1)").click();
    options = [...fixture.querySelectorAll(".o-popover .o-autocomplete-dropdown > div")];
    availableFields = options.map((el) => el.innerText);
    expect(availableFields).toEqual([
        "Active",
        "Creation Date",
        "Currency",
        "Date",
        "Display name",
        "field_with_array_agg",
        "Id",
        "Json Field",
        "Last Modified on",
        "Money!",
        "name",
        "Probability",
        "Product",
        "Properties",
        "Tags",
        "Users",
    ]);
});

test("Inserting a list preserves the ascending sorting from the list", async function () {
    const serverData = getBasicServerData();
    Partner._fields.foo.sortable = true;
    const { model } = await createSpreadsheetFromListView({
        serverData,
        orderBy: [{ name: "foo", asc: true }],
        linesNumber: 4,
    });
    expect(getEvaluatedCell(model, "A2").value <= getEvaluatedCell(model, "A3").value).not.toBe(
        undefined
    );
    expect(getEvaluatedCell(model, "A3").value <= getEvaluatedCell(model, "A4").value).not.toBe(
        undefined
    );
    expect(getEvaluatedCell(model, "A4").value <= getEvaluatedCell(model, "A5").value).not.toBe(
        undefined
    );
});

test("Inserting a list preserves the descending sorting from the list", async function () {
    const serverData = getBasicServerData();
    Partner._fields.foo.sortable = true;
    const { model } = await createSpreadsheetFromListView({
        serverData,
        orderBy: [{ name: "foo", asc: false }],
        linesNumber: 4,
    });
    expect(getEvaluatedCell(model, "A2").value >= getEvaluatedCell(model, "A3").value).not.toBe(
        undefined
    );
    expect(getEvaluatedCell(model, "A3").value >= getEvaluatedCell(model, "A4").value).not.toBe(
        undefined
    );
    expect(getEvaluatedCell(model, "A4").value >= getEvaluatedCell(model, "A5").value).not.toBe(
        undefined
    );
});

test("Sorting from the list is displayed in the properties panel", async function () {
    const serverData = getBasicServerData();
    Partner._fields.foo.sortable = true;
    Partner._fields.bar.sortable = true;
    const { model, env } = await createSpreadsheetFromListView({
        serverData,
        orderBy: [
            { name: "foo", asc: true },
            { name: "bar", asc: false },
        ],
        linesNumber: 4,
    });
    const [listId] = model.getters.getListIds();
    env.openSidePanel("LIST_PROPERTIES_PANEL", { listId });
    await animationFrame();
    expect(".o_sorting_rule_column:eq(0)").toHaveText("Bar");
    expect(".o_sorting_rule_column:eq(1)").toHaveText("Foo");
    /** Bar should be descending */
    expect(".o-select-order:eq(0)").toHaveText("Descending");
    /** Foo should be ascending */
    expect(".o-select-order:eq(1)").toHaveText("Ascending");
});

test("Opening the sidepanel of a list while the panel of another list is open updates the side panel", async function () {
    const { model, env } = await createSpreadsheetFromListView({});
    insertListInSpreadsheet(model, {
        model: "product",
        columns: [
            { name: "name", string: "Name" },
            { name: "active", string: "Active" },
        ],
    });

    const listIds = model.getters.getListIds();
    const fixture = getFixture();

    env.openSidePanel("LIST_PROPERTIES_PANEL", { listId: listIds[0] });
    await animationFrame();
    let modelName = fixture.querySelector(".o-section .o_model_name");
    expect(modelName).toHaveText("Partner (partner)");

    env.openSidePanel("LIST_PROPERTIES_PANEL", { listId: listIds[1] });
    await animationFrame();
    modelName = fixture.querySelector(".o-section .o_model_name");
    expect(modelName).toHaveText("Product (product)");
});

test("Duplicate a list from the side panel curates the list name", async function () {
    const serverData = getBasicServerData();
    Partner._fields.foo.sortable = true;
    const { model, env } = await createSpreadsheetFromListView({
        serverData,
        orderBy: [{ name: "foo", asc: true }],
    });
    const [listId] = model.getters.getListIds();
    const definition = model.getters.getListDefinition(listId);
    const listName = "Do not keep Unsupported characters: '-:-*-?-\\-[-]-/";
    model.dispatch("UPDATE_ODOO_LIST", {
        listId,
        list: { ...definition, name: listName },
    });
    env.openSidePanel("LIST_PROPERTIES_PANEL", { listId });
    await animationFrame();

    expect(model.getters.getListIds().length).toBe(1);
    expect(".o-sidePanelTitle").toHaveText("List #1");
    await contains(".os-cog-wheel-menu-icon").click();
    await contains(".o-popover [data-icon='content_copy']").click();
    expect(model.getters.getListIds().length).toBe(2);
    expect(".o-sidePanelTitle").toHaveText("List #2");
    const sheetIds = model.getters.getSheetIds();
    expect(sheetIds.length).toEqual(2);
    const sheetId = model.getters.getActiveSheetId();
    expect(sheetId).toBe(sheetIds[1]);
    expect(model.getters.getSheetName(sheetId)).toBe(
        sanitizeSheetName(listName + " (copy) (List #2)")
    );
});

test("List export from an action with an xml ID", async function () {
    const actionXmlId = "spreadsheet.partner_action";
    const { model } = await createSpreadsheetFromListView({ actionXmlId });
    expect(model.getters.getListDefinition("1").actionXmlId).toBe("spreadsheet.partner_action");
});

test("List cells are highlighted when their side panel is open", async function () {
    const { model, env } = await createSpreadsheetFromListView();
    const sheetId = model.getters.getActiveSheetId();
    env.openSidePanel("LIST_PROPERTIES_PANEL", { listId: "1" });
    await animationFrame();

    const range = model.getters.getRangeFromZone(
        sheetId,
        getZoneOfInsertedDataSource(model, "list", "1")
    );
    expect(getHighlightsFromStore(env)).toEqual([{ range, noFill: true }]);
    await contains(".o-sidePanelClose").click();
    expect(getHighlightsFromStore(env)).toEqual([]);
});

test("List cells are highlighted when hovering the list menu item", async function () {
    const { model, env } = await createSpreadsheetFromListView();
    await contains(".o-sidePanelClose").click();
    const sheetId = model.getters.getActiveSheetId();
    await contains(".o-topbar-top div[data-id='data']").click();
    await contains("div[data-name='list_data_sources']").click();

    await hover("div[data-name='item_list_1']");
    const range = model.getters.getRangeFromZone(
        sheetId,
        getZoneOfInsertedDataSource(model, "list", "1")
    );
    expect(getHighlightsFromStore(env)).toEqual([{ range, noFill: true }]);

    await leave("div[data-name='item_list_1']");
    expect(getHighlightsFromStore(env)).toEqual([]);
});

test("Inserting a grouped list ignore groups", async function () {
    const serverData = getBasicServerData();
    Partner._fields.foo.sortable = true;
    onRpc("partner", "web_read_group", ({ kwargs }) => {
        if (kwargs.groupby) {
            // The mock server cannot handle orderby count
            kwargs.order = "";
        }
    });
    const { model } = await createSpreadsheetFromListView({
        actions: async (fixture) => {
            // display the property which is an optional column
            await contains(".o_searchview_dropdown_toggler").click();
            await contains(".o_add_custom_group_menu").select("bar");
            await contains(".o_searchview_facet_label").click();
        },
        serverData,
        linesNumber: 4,
    });
    expect(getEvaluatedCell(model, "A2").value <= getEvaluatedCell(model, "A3").value).not.toBe(
        undefined
    );
});

test("Middle-click on 'See record' opens the record in a new tab", async function () {
    const { model, env } = await createSpreadsheetFromListView({
        serverData: {
            models: getBasicData(),
            views: {
                "partner,false,list": `
                    <list string="Partners">
                        <field name="foo"/>
                        <field name="bar"/>
                    </list>`,
                "partner,false,search": "<search/>",
            },
        },
    });

    mockService("action", {
        doAction(_, options) {
            expect.step("doAction");
            expect(options).toEqual({
                newWindow: true,
                viewType: "form",
            });
            return Promise.resolve(true);
        },
    });

    selectCell(model, "A2");
    const root = cellMenuRegistry.getAll().find((item) => item.id === "list_see_record");
    await root.execute(env, true);
    expect.verifySteps(["doAction"]);
});

test("readonly list side panel", async function () {
    const { model, env } = await createSpreadsheetFromListView();
    await doMenuAction(topbarMenuRegistry, ["data", "list_data_sources", "item_list_1"], env);
    await animationFrame();
    expect(".o-sidePanelBody > div.pe-none.opacity-50").toHaveCount(0);
    model.updateMode("readonly");
    await animationFrame();
    expect(".o-sidePanelBody > div.pe-none.opacity-50").toHaveCount(1);
    expect(".o-sidePanelBody > div.pe-none.opacity-50").toHaveAttribute("inert");
});

test("display list related filters panel", async function () {
    const { model } = await createSpreadsheetFromListView();
    const listId = model.getters.getListIds()[0];
    await addGlobalFilter(
        model,
        { id: "42", type: "relation", label: "Filter" },
        {
            list: {
                [listId]: {
                    chain: "product_id",
                    type: "many2one",
                },
            },
        }
    );
    await addGlobalFilter(model, { id: "43", type: "relation", label: "Filter 2" });
    expect(".o_side_panel_collapsible_title:contains(Matching 1 / 2 filters)").toHaveCount(1);
});

test("can sort a list from right click menu", async function () {
    const { model, env } = await createSpreadsheetFromListView();
    const [listId] = model.getters.getListIds();
    selectCell(model, "B1");
    const root = cellMenuRegistry.getAll().find((item) => item.id === "sorting_list");
    const sortAsc = root.children.find((item) => item.id === "list_sorting_asc");
    const sortDesc = root.children.find((item) => item.id === "list_sorting_desc");
    const noSorting = root.children.find((item) => item.id === "no_list_sorting");
    expect(model.getters.getListDefinition(listId).orderBy).toEqual([]);
    expect(noSorting.isActive(env)).toBe(true);

    sortAsc.execute(env);
    await waitForDataLoaded(model);
    expect(model.getters.getListDefinition(listId).orderBy).toEqual([{ name: "bar", asc: true }]);
    expect(sortAsc.isActive(env)).toBe(true);

    sortDesc.execute(env);
    await waitForDataLoaded(model);
    expect(model.getters.getListDefinition(listId).orderBy).toEqual([{ name: "bar", asc: false }]);
    expect(sortDesc.isActive(env)).toBe(true);

    noSorting.execute(env);
    await waitForDataLoaded(model);
    expect(model.getters.getListDefinition(listId).orderBy).toEqual([]);
    expect(noSorting.isActive(env)).toBe(true);
});
