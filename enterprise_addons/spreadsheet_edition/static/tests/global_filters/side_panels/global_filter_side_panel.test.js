import { render } from "@web/owl2/utils";
import { beforeEach, describe, expect, getFixture, test } from "@odoo/hoot";
import { waitFor } from "@odoo/hoot-dom";
import { stores, owlPlugins } from "@odoo/o-spreadsheet";
import { mountSpreadsheet } from "@spreadsheet/../tests/helpers/ui";
import { addGlobalFilterWithoutReload, updatePivot } from "@spreadsheet/../tests/helpers/commands";
import { defineSpreadsheetModels } from "@spreadsheet/../tests/helpers/data";
import { THIS_YEAR_GLOBAL_FILTER } from "@spreadsheet/../tests/helpers/global_filter";
import { contains, mountWithCleanup, onRpc } from "@web/../tests/web_test_helpers";

import { Component, onMounted, onWillUnmount, providePlugins, t, useProps, xml } from "@odoo/owl";
import { createSpreadsheetWithPivot } from "@spreadsheet/../tests/helpers/pivot";
import { createModelWithDataSource } from "@spreadsheet/../tests/helpers/model";
import { GlobalFiltersSidePanel } from "@spreadsheet_edition/bundle/global_filters/global_filters_side_panel";
import { editSelectComponent } from "@spreadsheet_edition/../tests/helpers/webclient_helpers";

const { useStoreProvider, ModelStore } = stores;

defineSpreadsheetModels();
describe.current.tags("desktop");

/**
 * @typedef {import("@spreadsheet").FixedPeriodDateGlobalFilter} FixedPeriodDateGlobalFilter
 */

let target;

const FILTER_CREATION_SELECTORS = {
    text: ".o_global_filter_new_text",
    date: ".o_global_filter_new_time",
    relation: ".o_global_filter_new_relation",
    boolean: ".o_global_filter_new_boolean",
    selection: ".o_global_filter_new_selection",
    numeric: ".o_global_filter_new_numeric",
};

class Parent extends Component {
    static template = xml`<div class="o-spreadsheet"><GlobalFiltersSidePanel/></div>`;
    static components = { GlobalFiltersSidePanel };

    props = useProps({
        model: t.object(),
    });

    setup() {
        providePlugins([owlPlugins.PopoverContainerPlugin], {
            getPopoverContainerRect: () =>
                getFixture().querySelector(".o-spreadsheet").getBoundingClientRect(),
        });
        const stores = useStoreProvider();
        stores.inject(ModelStore, this.props.model);

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

async function openSidePanel(model, env) {
    env.openSidePanel = env.openSidePanel ?? (() => {});
    await mountWithCleanup(Parent, { env, props: { model } });
}

async function replaceSidePanel(model, env) {
    env.replaceSidePanel = env.replaceSidePanel ?? (() => {});
    await mountWithCleanup(Parent, { env, props: { model } });
}

/**
 * @param {"text" | "date" | "relation" | "boolean" | "selection" | "numeric"} type
 */
async function clickCreateFilter(type) {
    await contains(FILTER_CREATION_SELECTORS[type]).click();
}

beforeEach(() => {
    target = getFixture();
});

test("Simple display", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    await openSidePanel(model, env);
    expect(".o_spreadsheet_global_filters_side_panel").toHaveCount(1);

    const buttons = target.querySelectorAll(".o_spreadsheet_global_filters_side_panel .o-button");
    expect(buttons.length).toBe(6);
    expect(buttons[0]).toHaveClass("o_global_filter_new_time");
    expect(buttons[1]).toHaveClass("o_global_filter_new_relation");
    expect(buttons[2]).toHaveClass("o_global_filter_new_text");
    expect(buttons[3]).toHaveClass("o_global_filter_new_boolean");
    expect(buttons[4]).toHaveClass("o_global_filter_new_selection");
    expect(buttons[5]).toHaveClass("o_global_filter_new_numeric");
});

test("Display with an existing 'Date' global filter", async function () {
    const { model } = await createSpreadsheetWithPivot();
    await mountSpreadsheet(model);
    const label = "This year";
    addGlobalFilterWithoutReload(model, {
        id: "42",
        type: "date",
        label,
    });

    await contains(".o_topbar_filter_icon").click();
    await waitFor(".o_spreadsheet_global_filters_side_panel");
    const sections = target.querySelectorAll(".o_spreadsheet_global_filters_side_panel .o-section");
    expect(sections.length).toBe(2);
    const labelElement = sections[0].querySelector(".o_side_panel_filter_label");
    expect(labelElement).toHaveText(label);

    await contains(sections[0].querySelector(".o-button-icon")).click();
    await contains(".o-menu-item[title='Edit']").click();
    await waitFor(".o_spreadsheet_filter_editor_side_panel");
    expect(".o_spreadsheet_filter_editor_side_panel .o_global_filter_label").toHaveValue(label);
});

test("Create a new boolean global filter", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    env.replaceSidePanel = (name) => expect.step(name);
    await replaceSidePanel(model, env);
    await clickCreateFilter("boolean");
    expect.verifySteps(["BOOLEAN_FILTERS_SIDE_PANEL"]);
});

test("Create a new selection global filter", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    env.replaceSidePanel = (name) => expect.step(name);
    await replaceSidePanel(model, env);
    await clickCreateFilter("selection");
    expect.verifySteps(["SELECTION_FILTERS_SIDE_PANEL"]);
});

test("Create a new numeric global filter", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    env.replaceSidePanel = (name) => expect.step(name);
    await replaceSidePanel(model, env);
    await clickCreateFilter("numeric");
    expect.verifySteps(["NUMERIC_FILTERS_SIDE_PANEL"]);
});

test("Create a new text global filter", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    env.replaceSidePanel = (name) => expect.step(name);
    await replaceSidePanel(model, env);
    await clickCreateFilter("text");
    expect.verifySteps(["TEXT_FILTER_SIDE_PANEL"]);
});

test("Create a new date global filter", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    env.replaceSidePanel = (name) => expect.step(name);
    await replaceSidePanel(model, env);
    await clickCreateFilter("date");
    expect.verifySteps(["DATE_FILTER_SIDE_PANEL"]);
});

test("Create a new relation global filter", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    env.replaceSidePanel = (name) => expect.step(name);
    await replaceSidePanel(model, env);
    await clickCreateFilter("relation");
    expect.verifySteps(["RELATION_FILTER_SIDE_PANEL"]);
});

test("Cannot create a relation filter without data source", async function () {
    const { model, env } = await createModelWithDataSource();
    await openSidePanel(model, env);
    expect(".o_global_filter_new_time").toHaveCount(1);
    expect(".o_global_filter_new_relation").toHaveCount(0);
    expect(".o_global_filter_new_text").toHaveCount(1);
});

test("Cannot create a selection filter without data source", async function () {
    const { model, env } = await createModelWithDataSource();
    await openSidePanel(model, env);
    expect(".o_global_filter_new_selection").toHaveCount(0);
});

test("Can create a relation filter with at least a data source", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    await openSidePanel(model, env);
    expect(".o_global_filter_new_time").toHaveCount(1);
    expect(".o_global_filter_new_relation").toHaveCount(1);
    expect(".o_global_filter_new_text").toHaveCount(1);
});

test("Can reorder filters with drag & drop", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    addGlobalFilterWithoutReload(model, THIS_YEAR_GLOBAL_FILTER);
    const id_1 = THIS_YEAR_GLOBAL_FILTER.id;
    const id_2 = "filter_id_2";
    addGlobalFilterWithoutReload(model, {
        ...THIS_YEAR_GLOBAL_FILTER,
        label: "second filter",
        id: id_2,
    });
    let filters = model.getters.getGlobalFilters();
    expect(filters[0].id).toBe(id_1);
    expect(filters[1].id).toBe(id_2);
    await openSidePanel(model, env);
    const handle = target.querySelector(".o-filter-drag-handle");
    const sections = target.querySelectorAll(".pivot_filter_section");

    await contains(handle, { visible: false }).dragAndDrop(sections[1], { position: "bottom" });

    filters = model.getters.getGlobalFilters();
    expect(filters[0].id).toBe(id_2);
    expect(filters[1].id).toBe(id_1);
});

test("Changing a global filter value applies immediately from side panel", async () => {
    const { model, env } = await createSpreadsheetWithPivot();
    addGlobalFilterWithoutReload(model, {
        id: "date_filter",
        type: "date",
        label: "My Date",
    });
    await openSidePanel(model, env);
    expect(model.getters.getGlobalFilterValue("date_filter")).toEqual(undefined);

    await contains(".o_spreadsheet_global_filters_side_panel input").click();
    await contains(".o-dropdown-item[data-id='today']").click();
    expect(model.getters.getGlobalFilterValue("date_filter")).toEqual({
        type: "relative",
        period: "today",
    });
});

test("Changing a global filter by deleting the value does not crash", async () => {
    const { model, env } = await createSpreadsheetWithPivot();
    addGlobalFilterWithoutReload(model, {
        id: "date_filter",
        type: "date",
        label: "My Date",
        defaultValue: "today",
    });
    await openSidePanel(model, env);
    expect(model.getters.getGlobalFilterValue("date_filter")).toEqual({
        type: "relative",
        period: "today",
    });
    await contains(".pivot_filter_section [data-icon='close']").click();
    expect(model.getters.getGlobalFilterValue("date_filter")).toEqual(undefined);
});

test("Changing operator updates global filter value immediately", async () => {
    const { model, env } = await createSpreadsheetWithPivot();
    addGlobalFilterWithoutReload(model, {
        id: "numeric_filter",
        type: "numeric",
        label: "Amount",
        defaultValue: { operator: "=", targetValue: 10 },
    });
    await openSidePanel(model, env);
    expect(model.getters.getGlobalFilterValue("numeric_filter")).toEqual({
        operator: "=",
        targetValue: 10,
    });

    await editSelectComponent(".o_spreadsheet_global_filters_side_panel .o-select", ">");
    expect(model.getters.getGlobalFilterValue("numeric_filter")).toEqual({
        operator: ">",
        targetValue: 10,
    });
});

test("Boolean global filter dispatches value when selecting set or not set", async () => {
    const { model, env } = await createSpreadsheetWithPivot();
    addGlobalFilterWithoutReload(model, {
        id: "boolean_filter",
        type: "boolean",
        label: "Active",
    });
    await openSidePanel(model, env);
    expect(model.getters.getGlobalFilterValue("boolean_filter")).toBe(undefined);

    await editSelectComponent(".o_spreadsheet_global_filters_side_panel .o-select", "set");
    expect(model.getters.getGlobalFilterValue("boolean_filter")).toEqual({
        operator: "set",
    });

    await editSelectComponent(".o_spreadsheet_global_filters_side_panel .o-select", "not set");
    expect(model.getters.getGlobalFilterValue("boolean_filter")).toEqual({
        operator: "not set",
    });
});

test("Changing operator without value updates local state but not the global filter", async () => {
    const { model, env } = await createSpreadsheetWithPivot();
    addGlobalFilterWithoutReload(model, {
        id: "numeric_filter",
        type: "numeric",
        label: "Amount",
    });
    await openSidePanel(model, env);
    expect(model.getters.getGlobalFilterValue("numeric_filter")).toBe(undefined);

    expect(".o_spreadsheet_global_filters_side_panel .o-select").toHaveText("is equal to");

    await editSelectComponent(".o_spreadsheet_global_filters_side_panel .o-select", ">");
    expect(".o_spreadsheet_global_filters_side_panel .o-select").toHaveText("greater than");
    expect(model.getters.getGlobalFilterValue("numeric_filter")).toBe(undefined);
});

test("Clearing a global filter clears the model value", async () => {
    const { model, env } = await createSpreadsheetWithPivot();
    addGlobalFilterWithoutReload(model, {
        id: "text_filter",
        type: "text",
        label: "Name",
        defaultValue: { operator: "ilike", strings: ["foo"] },
    });
    await openSidePanel(model, env);
    expect(model.getters.getGlobalFilterValue("text_filter")).toEqual({
        operator: "ilike",
        strings: ["foo"],
    });

    await contains(".o_spreadsheet_global_filters_side_panel [data-icon='close']").click();
    expect(model.getters.getGlobalFilterValue("text_filter")).toEqual(undefined);
});

test("Clearing the global filter value keeps the default value visible in the edit panel", async () => {
    const { model } = await createSpreadsheetWithPivot();
    await mountSpreadsheet(model);
    addGlobalFilterWithoutReload(model, {
        id: "text_filter",
        type: "text",
        label: "Name",
        defaultValue: { operator: "in", strings: ["foo"] },
    });
    await contains(".o_topbar_filter_icon").click();
    await waitFor(".o_spreadsheet_global_filters_side_panel");
    await contains(".o_spreadsheet_global_filters_side_panel [data-icon='close']").click();

    await contains(".o_spreadsheet_global_filters_side_panel .o-button-icon").click();
    await contains(".o-menu-item[title='Edit']").click();
    await waitFor(".o_spreadsheet_filter_editor_side_panel");
    expect(".o_spreadsheet_filter_editor_side_panel .o-select").toHaveText("is in");
    expect(".o_tag_badge_text").toHaveText("foo");
});

describe("Global filter cog menu", () => {
    const FILTER_PANEL_SECTION = ".o_spreadsheet_global_filters_side_panel .o-section";
    const COG_BUTTON = `${FILTER_PANEL_SECTION} .o-button-icon`;

    async function setupSpreadsheetWithGlobalFilter() {
        const { model } = await createSpreadsheetWithPivot();
        await mountSpreadsheet(model);
        addGlobalFilterWithoutReload(model, {
            id: "42",
            type: "date",
            label: "My filter",
        });
        await contains(".o_topbar_filter_icon").click();
        return model;
    }

    test("Edit action opens the editor panel", async function () {
        await setupSpreadsheetWithGlobalFilter();
        await contains(target.querySelector(COG_BUTTON)).click();
        await contains(".o-menu-item[title='Edit']").click();
        expect(".o-sidePanel .o_spreadsheet_filter_editor_side_panel").toHaveCount(1);
    });

    test("Delete action removes the global filter", async function () {
        const model = await setupSpreadsheetWithGlobalFilter();
        expect(model.getters.getGlobalFilter("42")).not.toBe(undefined);
        expect(target.querySelectorAll(FILTER_PANEL_SECTION)).toHaveLength(2);

        await contains(target.querySelector(COG_BUTTON)).click();
        await contains(".o-menu-item[title='Delete']").click();
        expect(model.getters.getGlobalFilter("42")).toBe(undefined);
        expect(target.querySelectorAll(FILTER_PANEL_SECTION)).toHaveLength(1);
    });
});

describe("integration", () => {
    test("suggestions", async () => {
        onRpc("get_search_view_archs", ({ args }) => {
            expect(args).toEqual([["action_partner"]]);
            return {
                partner: [
                    /*xml*/ `
                    <search>
                        <field name="product_id" string="My product filter"/>
                    </search>
                    `,
                ],
            };
        });
        const { model } = await createSpreadsheetWithPivot();
        await mountSpreadsheet(model);
        const [pivotId] = model.getters.getPivotIds();
        updatePivot(model, pivotId, { actionXmlId: "action_partner" });
        await contains(".o_topbar_filter_icon").click();
        await contains(".global-filter-suggestions button").click();
        await waitFor(".o_spreadsheet_filter_editor_side_panel");
        await contains(".o_global_filter_save").click();
        const globalFilter = model.getters.getGlobalFilters()[0];
        const filterId = globalFilter.id;
        expect(model.getters.getPivotFieldMatching(pivotId, filterId)).toEqual({
            chain: "product_id",
            type: "many2one",
        });
        expect(globalFilter).toEqual({
            id: filterId,
            domainOfAllowedValues: [],
            label: "My product filter",
            modelName: "product",
            type: "relation",
        });
        await waitFor(".o_spreadsheet_global_filters_side_panel");
        expect(".global-filter-suggestions").toHaveCount(0);
    });
});
