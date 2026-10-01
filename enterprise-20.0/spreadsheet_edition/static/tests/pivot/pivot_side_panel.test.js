import { render } from "@web/owl2/utils";
import { defineSpreadsheetModels, Partner } from "@spreadsheet/../tests/helpers/data";
import { describe, expect, getFixture, test, beforeEach } from "@odoo/hoot";
import { runAllTimers } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import { registries, stores, owlPlugins } from "@odoo/o-spreadsheet";
import { createSpreadsheetWithPivot } from "@spreadsheet/../tests/helpers/pivot";
import {
    addGlobalFilter,
    createSheet,
    deleteSheet,
    updatePivot,
} from "@spreadsheet/../tests/helpers/commands";
import {
    contains,
    fields,
    makeServerError,
    mountWithCleanup,
    onRpc,
    serverState,
} from "@web/../tests/web_test_helpers";
import { Component, onMounted, onWillUnmount, providePlugins, t, useProps, xml } from "@odoo/owl";
import { PivotDetailsSidePanel } from "@spreadsheet_edition/bundle/pivot/side_panels/pivot_details_side_panel";
const { useStore, useStoreProvider, ModelStore, SidePanelStore } = stores;
import {
    editSelectComponent,
    getFieldItem,
} from "@spreadsheet_edition/../tests/helpers/webclient_helpers";

defineSpreadsheetModels();
describe.current.tags("desktop");

const { evaluationPluginRegistry, pivotRegistry } = registries;

let target;

beforeEach(() => {
    target = getFixture();
});

class Parent extends Component {
    // We need to wrap the component in a div with `o-spreadsheet` to have a correct portal target for spreadsheet popovers
    static template = xml/* xml */ `
        <div class="o-spreadsheet">
            <PivotDetailsSidePanel onCloseSidePanel="this.props.onCloseSidePanel" pivotId="this.props.pivotId"/>
        </div>
    `;
    static components = { PivotDetailsSidePanel };

    props = useProps({
        model: t.object(),
        pivotId: t.string(),
        onCloseSidePanel: t.function(),
    });

    setup() {
        providePlugins([owlPlugins.PopoverContainerPlugin], {
            getPopoverContainerRect: () =>
                getFixture().querySelector(".o-spreadsheet").getBoundingClientRect(),
        });
        const stores = useStoreProvider();
        stores.inject(ModelStore, this.props.model);
        const sidePanelStore = useStore(SidePanelStore);
        sidePanelStore.open("PivotSidePanel", this.props);

        onMounted(() => {
            this.props.model.on("update", this, () => render(this, true));
            stores.on("store-updated", this, () => render(this, true));
        });
        onWillUnmount(() => {
            this.props.model.off("update", this);
            stores.off("store-updated", this);
        });
    }
}

async function openSidePanel(model, env, pivotId, onCloseSidePanel = () => {}) {
    env.notifyUser = env.notifyUser || (() => {});
    env.openSidePanel = env.openSidePanel || (() => {});
    await mountWithCleanup(Parent, { env, props: { model, pivotId, onCloseSidePanel } });
}

async function replaceSidePanel(model, env, pivotId, onCloseSidePanel = () => {}) {
    env.notifyUser = env.notifyUser || (() => {});
    env.replaceSidePanel = env.replaceSidePanel || (() => {});
    await mountWithCleanup(Parent, { env, props: { model, pivotId, onCloseSidePanel } });
}

test("Open pivot properties", async function () {
    const { pivotId, env, model } = await createSpreadsheetWithPivot();
    await openSidePanel(model, env, pivotId);
    expect(".o_spreadsheet_pivot_side_panel").toHaveCount(1);
});

test("Pivot properties panel shows ascending sorting", async function () {
    const { model, env, pivotId } = await createSpreadsheetWithPivot();
    updatePivot(model, pivotId, {
        sortedColumn: {
            domain: [{ value: 1, field: "foo", type: "integer" }],
            measure: "probability:avg",
            order: "asc",
        },
    });
    await openSidePanel(model, env, pivotId);
    expect(".o-pivot-sort").toHaveCount(1);
    expect(".o-pivot-sort").toHaveText(/ascending/);

    const pivotSortingNodes = target.querySelectorAll(".o-sort-card");
    expect(pivotSortingNodes[0].textContent).toBe("Foo = 1");
    expect(pivotSortingNodes[1].textContent).toBe("Measure = Probability");
});

test("Pivot properties panel shows descending sorting", async function () {
    const { model, pivotId, env } = await createSpreadsheetWithPivot();
    updatePivot(model, pivotId, {
        sortedColumn: {
            domain: [{ value: 1, field: "foo", type: "integer" }],
            measure: "probability:avg",
            order: "desc",
        },
    });
    await openSidePanel(model, env, pivotId);

    expect(".o-pivot-sort").toHaveCount(1);
    expect(".o-pivot-sort").toHaveText(/descending/);

    const pivotSortingNodes = target.querySelectorAll(".o-sort-card");
    expect(pivotSortingNodes[0].textContent).toBe("Foo = 1");
    expect(pivotSortingNodes[1].textContent).toBe("Measure = Probability");
});

test("Removing the measure removes the sortedColumn", async function () {
    const { model, pivotId, env } = await createSpreadsheetWithPivot();
    updatePivot(model, pivotId, {
        sortedColumn: {
            domain: [{ value: 1, field: "foo", type: "integer" }],
            measure: "probability:avg",
            order: "asc",
        },
    });
    await openSidePanel(model, env, pivotId);
    expect(model.getters.getPivot(pivotId).definition.sortedColumn).not.toBe(undefined);

    await contains(".pivot-measure [data-icon='delete_f']").click();
    expect(model.getters.getPivot(pivotId).definition.sortedColumn).toBe(undefined);
});

test("Removing a column removes the sortedColumn", async function () {
    const { model, pivotId, env } = await createSpreadsheetWithPivot();
    updatePivot(model, pivotId, {
        sortedColumn: {
            domain: [{ value: 1, field: "foo", type: "integer" }],
            measure: "probability:avg",
            order: "asc",
        },
    });
    await openSidePanel(model, env, pivotId);

    expect(model.getters.getPivot(pivotId).definition.sortedColumn).not.toBe(undefined);
    await contains(".pivot-dimension [data-icon='delete_f']").click();
    expect(model.getters.getPivot(pivotId).definition.sortedColumn).toBe(undefined);
});

test("Open pivot properties properties with non-loaded field", async function () {
    const PivotUIPlugin = evaluationPluginRegistry.get("pivot_ui");
    const { model, pivotId, env } = await createSpreadsheetWithPivot();
    const pivotPlugin = model["handlers"].find((handler) => handler instanceof PivotUIPlugin);
    const dataSource = Object.values(pivotPlugin.pivots)[0];
    // remove all loading promises and the model to simulate the data source is not loaded
    dataSource._loadPromise = undefined;
    dataSource._createModelPromise = undefined;
    dataSource._model = undefined;
    await openSidePanel(model, env, pivotId);
    expect(".o_spreadsheet_pivot_side_panel").toHaveCount(1);
});

test("Update the pivot title from the side panel", async function () {
    const { model, pivotId, env } = await createSpreadsheetWithPivot();
    await openSidePanel(model, env, pivotId);
    const target = await contains(".os-input");
    await target.click();
    await target.edit("new name");
    expect(model.getters.getPivotName(pivotId)).toBe("new name");
});

test("Duplicate the pivot from the side panel", async function () {
    const { model, pivotId, env } = await createSpreadsheetWithPivot();
    env.openSidePanel = (name, props) => {
        expect.step(name);
        expect.step(props.pivotId);
    };
    await openSidePanel(model, env, pivotId);

    expect(model.getters.getPivotIds().length).toBe(1);
    expect(".os-pivot-title").toHaveValue("Partner Pivot");

    await contains(".os-cog-wheel-menu-icon").click();
    await contains(".o-popover [data-icon='content_copy']").click();
    expect(model.getters.getPivotIds().length).toBe(2);
    const duplicatedPivotId = model.getters.getPivotIds()[1];
    expect.verifySteps(["PivotSidePanel", duplicatedPivotId]);
    expect(model.getters.getPivotCoreDefinition(duplicatedPivotId).name).toBe(
        "Partner Pivot (copy)"
    );
});

test("A warning is displayed in the side panel if the pivot is unused", async function () {
    const { model, pivotId, env } = await createSpreadsheetWithPivot();
    await openSidePanel(model, env, pivotId);

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

test("An error is displayed in the side panel if the pivot has invalid model", async function () {
    const { model, pivotId, env } = await createSpreadsheetWithPivot({
        mockRPC: async function (route, { model, method, kwargs }) {
            if (model === "unknown" && method === "fields_get") {
                throw makeServerError({ code: 404 });
            }
        },
    });
    const pivot = model.getters.getPivotCoreDefinition(pivotId);
    env.model.dispatch("UPDATE_PIVOT", {
        pivotId,
        pivot: {
            ...pivot,
            model: "unknown",
        },
    });
    await openSidePanel(model, env, pivotId);

    expect(".o-validation-error").toHaveCount(1);
});

test("can drag a column dimension to row", async function () {
    const { model, env, pivotId } = await createSpreadsheetWithPivot();
    await openSidePanel(model, env, pivotId);
    await contains(".pivot-defer-update input").click();
    expect("pivot-defer-update").toHaveCount(0, {
        message: "defer updates is not displayed by default",
    });
    expect(".pivot-defer-update .btn").toHaveCount(0, {
        message: "it should not show the update/discard buttons",
    });
    let definition = JSON.parse(JSON.stringify(model.getters.getPivotCoreDefinition(pivotId)));
    expect(definition.columns).toEqual([{ fieldName: "foo" }]);
    expect(definition.rows).toEqual([{ fieldName: "bar" }]);
    await contains(".pivot-dimensions div:nth-child(2)").dragAndDrop(
        ".pivot-dimensions div:nth-child(4)",
        { position: "bottom" }
    );
    await animationFrame();
    expect(".pivot-defer-update [data-icon='undo']").toHaveCount(1);
    expect(".pivot-defer-update .sp_apply_update").toHaveCount(1);
    // TODO use a snapshot
    definition = JSON.parse(JSON.stringify(model.getters.getPivotCoreDefinition(pivotId)));
    // update is not applied until the user clicks on the save button
    expect(definition.columns).toEqual([{ fieldName: "foo" }]);
    expect(definition.rows).toEqual([{ fieldName: "bar" }]);
    await contains(".pivot-defer-update .o-button-link").click();
    expect(".pivot-defer-update .btn").toHaveCount(0, {
        message: "it should not show the update/discard buttons",
    });
    definition = JSON.parse(JSON.stringify(model.getters.getPivotCoreDefinition(pivotId)));
    expect(definition.columns).toEqual([]);
    expect(definition.rows).toEqual([{ fieldName: "bar" }, { fieldName: "foo" }]);
});

test("updates are applied immediately after defer update checkbox has been unchecked", async function () {
    const { model, env, pivotId } = await createSpreadsheetWithPivot();
    await openSidePanel(model, env, pivotId);
    await contains(".pivot-dimensions div:nth-child(2)").dragAndDrop(
        ".pivot-dimensions div:nth-child(4)",
        { position: "bottom" }
    );
    await animationFrame();
    expect(".pivot-defer-update .btn").toHaveCount(0, {
        message: "it should not show the update/discard buttons",
    });
    const definition = JSON.parse(JSON.stringify(model.getters.getPivotCoreDefinition(pivotId)));
    expect(definition.columns).toEqual([]);
    expect(definition.rows).toEqual([{ fieldName: "bar" }, { fieldName: "foo" }]);
});

test("remove pivot dimension", async function () {
    const { model, env, pivotId } = await createSpreadsheetWithPivot();
    await openSidePanel(model, env, pivotId);
    await contains(".pivot-defer-update input").click();
    await contains(".pivot-dimensions [data-icon='delete_f']").click();
    await animationFrame();
    await contains(".pivot-defer-update .o-button-link").click();
    const definition = JSON.parse(JSON.stringify(model.getters.getPivotCoreDefinition(pivotId)));
    expect(definition.columns).toEqual([]);
    expect(definition.rows).toEqual([{ fieldName: "bar" }]);
});

test("remove pivot date time dimension", async function () {
    const { model, env, pivotId } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="date" type="row" interval="year"/>
                <field name="date" type="row" interval="month"/>
                <field name="probability" type="measure"/>
            </pivot>
        `,
    });
    await openSidePanel(model, env, pivotId);
    await contains(".pivot-defer-update input").click();
    await contains(".pivot-dimensions [data-icon='delete_f']").click();
    await animationFrame();
    await contains(".pivot-defer-update .o-button-link").click();
    const definition = JSON.parse(JSON.stringify(model.getters.getPivotCoreDefinition(pivotId)));
    expect(definition.rows).toEqual([{ fieldName: "date", granularity: "month" }]);
});

test("add column dimension", async function () {
    const { model, env, pivotId } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="probability" type="measure"/>
            </pivot>
        `,
    });
    await openSidePanel(model, env, pivotId);
    await contains(".add-dimension.o-button").click();
    await contains(
        ".o_popover_field_selector .o_model_field_selector_popover_item[data-name='bar'] button"
    ).click();
    await contains(".pivot-defer-update .o-checkbox").click();
    const definition = JSON.parse(JSON.stringify(model.getters.getPivotCoreDefinition(pivotId)));
    expect(definition.columns).toEqual([{ fieldName: "bar", order: "asc" }]);
    expect(definition.rows).toEqual([]);
});

test("add row dimension", async function () {
    const { model, env, pivotId } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="probability" type="measure"/>
            </pivot>
        `,
    });
    await openSidePanel(model, env, pivotId);
    await contains(".add-dimension.o-button:eq(1)").click();
    await contains(
        ".o_popover_field_selector .o_model_field_selector_popover_item[data-name='bar'] button"
    ).click();
    await contains(".pivot-defer-update .o-checkbox").click();
    const definition = JSON.parse(JSON.stringify(model.getters.getPivotCoreDefinition(pivotId)));
    expect(definition.columns).toEqual([]);
    expect(definition.rows).toEqual([{ fieldName: "bar", order: "asc" }]);
});

test("add column dimension on a related model", async function () {
    const { model, env, pivotId } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="probability" type="measure"/>
            </pivot>
        `,
    });
    await openSidePanel(model, env, pivotId);
    await contains(".add-dimension.o-button").click();
    await contains(
        ".o_popover_field_selector .o_model_field_selector_popover_item[data-name='product_id'] .o_model_field_selector_popover_item_relation"
    ).click();
    await contains(
        ".o_popover_field_selector .o_model_field_selector_popover_item[data-name='active'] button"
    ).click();
    expect("[data-icon='warning']").toHaveCount(0);
    expect(".pivot-dimension:first .o-fw-bold").toHaveText("Product > Active");
    await contains(".pivot-defer-update .o-checkbox").click();
    const definition = JSON.parse(JSON.stringify(model.getters.getPivotCoreDefinition(pivotId)));
    expect(definition.columns).toEqual([{ fieldName: "product_id.active", order: "asc" }]);
    expect(definition.rows).toEqual([]);
    expect(".pivot-dimension:first .o-fw-bold").toHaveText("Product > Active");
});

test("add row dimension on a related model", async function () {
    const { model, env, pivotId } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="probability" type="measure"/>
            </pivot>
        `,
    });
    await openSidePanel(model, env, pivotId);
    await contains(".add-dimension.o-button:eq(1)").click();
    await contains(
        ".o_popover_field_selector .o_model_field_selector_popover_item[data-name='product_id'] .o_model_field_selector_popover_item_relation"
    ).click();
    await contains(
        ".o_popover_field_selector .o_model_field_selector_popover_item[data-name='active'] button"
    ).click();
    expect("[data-icon='warning']").toHaveCount(0);
    expect(".pivot-dimension:first .o-fw-bold").toHaveText("Product > Active");
    await contains(".pivot-defer-update .o-checkbox").click();
    const definition = JSON.parse(JSON.stringify(model.getters.getPivotCoreDefinition(pivotId)));
    expect(definition.columns).toEqual([]);
    expect(definition.rows).toEqual([{ fieldName: "product_id.active", order: "asc" }]);
    expect(".pivot-dimension:first .o-fw-bold").toHaveText("Product > Active");
});

test("single non-relation dimension is filtered out after selection", async function () {
    const { model, env, pivotId } = await createSpreadsheetWithPivot();
    await openSidePanel(model, env, pivotId);
    const fixture = getFixture();

    await contains(".add-dimension.o-button").click();
    getFieldItem("id", fixture).querySelector("button").click();
    await contains(".pivot-defer-update .o-checkbox").click();

    await contains(".add-dimension.o-button").click();
    expect(getFieldItem("id", fixture)).toBe(null);
});

test("date/datetime field can be re-selected because of different granularities", async function () {
    const { model, env, pivotId } = await createSpreadsheetWithPivot();
    await openSidePanel(model, env, pivotId);
    const fixture = getFixture();

    await contains(".add-dimension.o-button").click();
    getFieldItem("date", fixture).querySelector("button").click();
    await contains(".pivot-defer-update .o-checkbox").click();

    await contains(".add-dimension.o-button").click();
    const item = getFieldItem("date", fixture);
    expect(item).not.toBe(null);
    expect(item.getAttribute("data-tooltip")).toBe(null);
    expect(item.querySelector(".o_model_field_selector_popover_item_name").disabled).toBe(false);
});

test("date/datetime field is filtered out once every granularity is used", async function () {
    const { model, env, pivotId } = await createSpreadsheetWithPivot();
    const dateGranularities = pivotRegistry.get("ODOO").dateGranularities;
    updatePivot(model, pivotId, {
        rows: dateGranularities.map((granularity) => ({ fieldName: "date", granularity })),
    });
    await openSidePanel(model, env, pivotId);
    const fixture = getFixture();

    await contains(".add-dimension.o-button").click();
    expect(getFieldItem("date", fixture)).toBe(null);
});

test("relation field cannot be re-selected but subfields stay accessible", async function () {
    const { model, env, pivotId } = await createSpreadsheetWithPivot();
    await openSidePanel(model, env, pivotId);
    const fixture = getFixture();

    await contains(".add-dimension.o-button").click();
    getFieldItem("product_id", fixture).querySelector("button").click();
    await contains(".pivot-defer-update .o-checkbox").click();

    await contains(".add-dimension.o-button").click();
    const item = getFieldItem("product_id", fixture);
    expect(item.getAttribute("data-tooltip")).toBe("Already present in the source");
    expect(item.querySelector(".o_model_field_selector_popover_item_name").disabled).toBe(true);
    expect(item.querySelector(".o_model_field_selector_popover_item_relation").disabled).toBe(
        false
    );
});

test("Cannot follow relation of a non store field", async function () {
    Partner._fields.product_id = fields.Many2one({
        string: "Product",
        relation: "product",
        store: false,
    });
    const { model, env, pivotId } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="probability" type="measure"/>
            </pivot>
        `,
    });
    await openSidePanel(model, env, pivotId);
    await contains(".add-dimension.o-button:eq(1)").click();
    expect(
        ".o_popover_field_selector .o_model_field_selector_popover_item[data-name='product_id'] .o_model_field_selector_popover_item_relation"
    ).toHaveCount(0);
});

test("Cannot follow relation of a m2m field", async function () {
    Partner._fields.product_ids = fields.Many2many({
        relation: "product",
        store: true,
        searchable: true,
        string: "Product",
    });
    const { model, env, pivotId } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="probability" type="measure"/>
            </pivot>
        `,
    });
    await openSidePanel(model, env, pivotId);
    await contains(".add-dimension.o-button:eq(1)").click();
    expect(
        ".o_popover_field_selector .o_model_field_selector_popover_item[data-name='product_ids'] .o_model_field_selector_popover_item_relation"
    ).toHaveCount(0);
});

test("select dimensions with arrow keys", async function () {
    const { model, env, pivotId } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="probability" type="measure"/>
            </pivot>
        `,
    });
    const fixture = getFixture();
    await openSidePanel(model, env, pivotId);
    await contains(".add-dimension.o-button").click();
    let options = [
        ...fixture.querySelectorAll(
            ".o_popover_field_selector .o_model_field_selector_popover_item"
        ),
    ];
    expect(options[0].className.includes("active")).toBe(true);
    expect(options[1].className.includes("active")).toBe(false);
    await contains(".o_model_field_selector_popover_search input").press("ArrowDown");
    options = [
        ...fixture.querySelectorAll(
            ".o_popover_field_selector .o_model_field_selector_popover_item"
        ),
    ];
    expect(options[0].className.includes("active")).toBe(false);
    expect(options[1].className.includes("active")).toBe(true);
    await contains(".o_model_field_selector_popover_search input").press("ArrowUp");
    options = [
        ...fixture.querySelectorAll(
            ".o_popover_field_selector .o_model_field_selector_popover_item"
        ),
    ];
    expect(options[0].className.includes("active")).toBe(true);
    expect(options[1].className.includes("active")).toBe(false);
    await contains(".o_model_field_selector_popover_search input").press("Enter");
    await contains(".pivot-defer-update .o-checkbox").click();
    const definition = JSON.parse(JSON.stringify(model.getters.getPivotCoreDefinition(pivotId)));
    expect(definition.columns).toEqual([{ fieldName: "bar", order: "asc" }]);
    expect(definition.rows).toEqual([]);
});

test("escape key closes the autocomplete popover", async function () {
    const { model, env, pivotId } = await createSpreadsheetWithPivot();
    await openSidePanel(model, env, pivotId);
    await contains(".add-dimension.o-button").click();
    expect(".o_model_field_selector_popover_search input").toHaveCount(1);
    await contains(".o_model_field_selector_popover_search input").press("Escape");
    expect(".o_model_field_selector_popover_search input").toHaveCount(0);
});

test("add pivot dimension input autofocus", async function () {
    const { model, env, pivotId } = await createSpreadsheetWithPivot();
    await openSidePanel(model, env, pivotId);
    await contains(".add-dimension.o-button").click();
    expect(".o_model_field_selector_popover_search input").toBeFocused();
    await contains(".o_model_field_selector_popover_search input").press("Escape");
    await contains(".add-dimension.o-button").click();
    expect(".o_model_field_selector_popover_search input").toBeFocused();
});

test("add and search dimension", async function () {
    const foo = fields.Integer({
        string: "Foo",
        store: true,
        searchable: true,
        aggregator: "sum",
        groupable: true,
    });
    const foobar = fields.Char({
        string: "FooBar",
        store: true,
        sortable: true,
        groupable: true,
        searchable: true,
    });
    Partner._fields.foobar = foobar;
    Partner._fields.foo = foo;
    Partner._records = [{ id: 1, foo: 12, bar: true, foobar: "foobar", probability: 10 }];
    const { model, env, pivotId } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="probability" type="measure"/>
            </pivot>
        `,
    });
    await openSidePanel(model, env, pivotId);
    await contains(".pivot-defer-update input").click();
    await contains(".add-dimension.o-button").click();
    await contains(".o_model_field_selector_popover_search input").edit("fooba", {
        confirm: false,
    });
    await runAllTimers();
    await animationFrame();
    await contains(".o_model_field_selector_popover_search input").press("Enter");
    expect(model.getters.getPivotCoreDefinition(pivotId).columns).toEqual([]);
    expect(model.getters.getPivotCoreDefinition(pivotId).rows).toEqual([]);
    await contains(".pivot-defer-update input").click();
    expect(
        JSON.parse(JSON.stringify(model.getters.getPivotCoreDefinition(pivotId))).columns
    ).toEqual([{ fieldName: "foobar", order: "asc" }]);
    expect(model.getters.getPivotCoreDefinition(pivotId).rows).toEqual([]);
});

test("remove pivot measure", async function () {
    const { model, env, pivotId } = await createSpreadsheetWithPivot();
    await openSidePanel(model, env, pivotId);
    await contains(".pivot-defer-update input").click();
    await contains(".pivot-dimensions [data-icon='delete_f']:last").click();
    await animationFrame();
    await contains(".pivot-defer-update .o-button-link").click();
    const definition = JSON.parse(JSON.stringify(model.getters.getPivotCoreDefinition(pivotId)));
    expect(definition.columns).toEqual([{ fieldName: "foo" }]);
    expect(definition.rows).toEqual([{ fieldName: "bar" }]);
    expect(definition.measures).toEqual([]);
});

test("add measure", async function () {
    const { model, env, pivotId } = await createSpreadsheetWithPivot();
    await openSidePanel(model, env, pivotId);
    const fixture = getFixture();
    await contains(fixture.querySelectorAll(".add-dimension.o-button")[2]).click();
    await contains(fixture.querySelectorAll(".o-popover .o-autocomplete-value")[0]).click();
    await contains(".pivot-defer-update .o-checkbox").click();
    const definition = JSON.parse(JSON.stringify(model.getters.getPivotCoreDefinition(pivotId)));
    expect(definition.columns).toEqual([{ fieldName: "foo" }]);
    expect(definition.rows).toEqual([{ fieldName: "bar" }]);
    expect(definition.measures).toEqual([
        { id: "probability:avg", fieldName: "probability", aggregator: "avg" },
        { id: "__count:sum", fieldName: "__count", aggregator: "sum" },
    ]);
});

test("change measure aggregator", async function () {
    const { model, env, pivotId } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="probability" type="measure"/>
            </pivot>
        `,
    });
    await openSidePanel(model, env, pivotId);
    await contains(".pivot-defer-update input").click();
    expect(".pivot-measure .o-select").toHaveText("Average");
    await editSelectComponent(".pivot-measure .o-select", "min");
    await contains(".pivot-defer-update .o-button-link").click();
    expect(".pivot-measure .o-select").toHaveText("Minimum");
    const definition = model.getters.getPivotCoreDefinition(pivotId);
    expect(definition.measures).toEqual([
        {
            id: "probability:min",
            fieldName: "probability",
            aggregator: "min",
            userDefinedName: undefined,
            computedBy: undefined,
            format: undefined,
            isHidden: undefined,
            display: undefined,
        },
    ]);
});

test("pivot with a reference field measure", async function () {
    const currency_reference = fields.Reference({
        string: "Currency reference",
        store: true,
        sortable: true,
        groupable: true,
        searchable: true,
        aggregator: "count_distinct",
        selection: [["res.currency", "Currency"]],
    });
    Partner._fields.currency_reference = currency_reference;
    Partner._records = [{ id: 1, currency_reference: "res.currency,1" }];

    const { model, env, pivotId } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="currency_reference" type="measure"/>
            </pivot>
        `,
    });
    await openSidePanel(model, env, pivotId);
    expect(".pivot-measure .o-select").toHaveText("Count Distinct");
});

test("change dimension order", async function () {
    const { model, env, pivotId } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="foo" type="row"/>
                <field name="probability" type="measure"/>
            </pivot>
        `,
    });
    await openSidePanel(model, env, pivotId);
    await contains(".pivot-defer-update input").click();
    const fixture = getFixture();
    expect(fixture.querySelector(".pivot-dimensions .o-select")).toHaveText("Unsorted");
    await editSelectComponent(".pivot-dimensions .o-select", "desc");
    expect(fixture.querySelector(".pivot-dimensions .o-select")).toHaveText("Descending");
    await contains(".pivot-defer-update .o-button-link").click();
    let definition = JSON.parse(JSON.stringify(model.getters.getPivotCoreDefinition(pivotId)));
    expect(definition.rows).toEqual([{ fieldName: "foo", order: "desc" }]);

    // reset to automatic
    await editSelectComponent(".pivot-dimensions .o-select", "");
    await contains(".pivot-defer-update .o-button-link").click();
    definition = JSON.parse(JSON.stringify(model.getters.getPivotCoreDefinition(pivotId)));
    expect(definition.rows).toEqual([{ fieldName: "foo" }]);
});

test("change date dimension granularity", async function () {
    const { model, env, pivotId } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="date" interval="day" type="row"/>
                <field name="probability" type="measure"/>
            </pivot>
        `,
    });
    await openSidePanel(model, env, pivotId);
    const fixture = getFixture();
    await contains(".pivot-defer-update input").click();
    expect(fixture.querySelector(".pivot-dimensions .o-select")).toHaveText("Day");
    await editSelectComponent(fixture.querySelector(".pivot-dimensions .o-select"), "week");
    expect(fixture.querySelector(".pivot-dimensions .o-select")).toHaveText("Week & Year");
    await contains(".pivot-defer-update .o-button-link").click();
    const definition = JSON.parse(JSON.stringify(model.getters.getPivotCoreDefinition(pivotId)));
    expect(definition.rows).toEqual([{ fieldName: "date", granularity: "week" }]);
});

test("pivot with twice the same date field with different granularity", async function () {
    const { model, env, pivotId } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="date" interval="year" type="row"/>
                <field name="date" interval="day" type="row"/>
                <field name="probability" type="measure"/>
            </pivot>
        `,
    });
    await openSidePanel(model, env, pivotId);
    const fixture = getFixture();
    const firstDateGroup = fixture.querySelectorAll(".pivot-dimensions .o-select")[0];
    const secondDateGroup = fixture.querySelectorAll(".pivot-dimensions .o-select")[2];

    expect(firstDateGroup).toHaveText("Year");
    await contains(firstDateGroup).click();
    expect(".o-spreadsheet .o-popover").toHaveText(
        "Year\nQuarter\nQuarter & Year\nMonth\nMonth & Year\nWeek\nWeek & Year\nDay of Month\nDay of Week"
    );

    expect(secondDateGroup).toHaveText("Day");
    await contains(secondDateGroup).click();
    expect(".o-spreadsheet .o-popover").toHaveText(
        "Quarter\nQuarter & Year\nMonth\nMonth & Year\nWeek\nWeek & Year\nDay of Month\nDay\nDay of Week"
    );
});

test("Can change measure display as from the side panel", async function () {
    const { model, env, pivotId } = await createSpreadsheetWithPivot();
    env.replaceSidePanel = (name, props) => {
        expect.step(name);
    };
    await replaceSidePanel(model, env, pivotId);

    await contains(".pivot-measure [data-icon='settings_f']").click();
    expect.verifySteps(["PivotMeasureDisplayPanel"]);
});

test("display pivot related filters panel", async function () {
    const { model, env, pivotId } = await createSpreadsheetWithPivot();
    await openSidePanel(model, env, pivotId);
    await addGlobalFilter(
        model,
        { id: "42", type: "relation", label: "Filter" },
        {
            pivot: {
                [pivotId]: {
                    chain: "product_id",
                    type: "many2one",
                },
            },
        }
    );
    await addGlobalFilter(model, { id: "43", type: "relation", label: "Filter 2" });
    expect(".o_side_panel_collapsible_title:contains(Matching 1 / 2 filters)").toHaveCount(1);
});

test("SidepanelModelFieldSelectorPopover in debug mode for column", async function () {
    serverState.debug = "1";
    const { model, env, pivotId } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="probability" type="measure"/>
            </pivot>
        `,
    });
    await openSidePanel(model, env, pivotId);
    await contains(".add-dimension.o-button:eq(0)").click();
    expect(
        "li.o_model_field_selector_popover_item div.o_model_field_selector_popover_item_title"
    ).toHaveCount(12);
});

test("side panel does not blink to the invalid-model state during definition reload", async function () {
    const { model, env, pivotId } = await createSpreadsheetWithPivot();
    await openSidePanel(model, env, pivotId);
    expect(".o_model_name").toHaveCount(1);
    expect(".o-validation-error").toHaveCount(0);

    const def = Promise.withResolvers();
    onRpc("partner", "formatted_read_grouping_sets", () => def.promise);
    await contains(".pivot-dimensions div:nth-child(2)").dragAndDrop(
        ".pivot-dimensions div:nth-child(4)",
        { position: "bottom" }
    );
    // The side panel must remain in a valid state during the reload.
    expect(".o_model_name").toHaveCount(1);
    expect(".o-validation-error").toHaveCount(0);

    def.resolve();
    await animationFrame();
    expect(".o_model_name").toHaveCount(1);
    expect(".o-validation-error").toHaveCount(0);
});

test("SidepanelModelFieldSelectorPopover in debug mode for row", async function () {
    serverState.debug = "1";
    const { model, env, pivotId } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="probability" type="measure"/>
            </pivot>
        `,
    });
    await openSidePanel(model, env, pivotId);
    await contains(".add-dimension.o-button:eq(1)").click();
    expect(
        "li.o_model_field_selector_popover_item div.o_model_field_selector_popover_item_title"
    ).toHaveCount(12);
});
