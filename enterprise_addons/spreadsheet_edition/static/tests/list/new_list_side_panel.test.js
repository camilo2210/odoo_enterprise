import { defineSpreadsheetModels, getBasicServerData } from "@spreadsheet/../tests/helpers/data";
import { describe, expect, test } from "@odoo/hoot";
import { stores, helpers } from "@odoo/o-spreadsheet";
import { createSpreadsheetWithList } from "@spreadsheet/../tests/helpers/list";
import { contains, mountWithCleanup } from "@web/../tests/web_test_helpers";
import { Component, onMounted, onWillUnmount, t, useProps, xml } from "@odoo/owl";
import { getCellValue } from "@spreadsheet/../tests/helpers/getters";
import { NewListSidePanel } from "@spreadsheet_edition/bundle/list/side_panels/new_list_sidepanel/new_list_sidepanel";
import { render } from "@web/owl2/utils";
const { useStoreProvider, ModelStore } = stores;
const { toZone } = helpers;

defineSpreadsheetModels();
describe.current.tags("desktop");

class Parent extends Component {
    static template = xml/* xml */ `
        <NewListSidePanel onCloseSidePanel="() => {}"/>
    `;
    static components = { NewListSidePanel };

    props = useProps({
        model: t.object(),
    });

    setup() {
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
    env.notifyUser = env.notifyUser || (() => {});
    env.openSidePanel = env.openSidePanel || (() => {});
    await mountWithCleanup(Parent, { env, props: { model } });
}

test("Open new list side panel", async function () {
    const { env, model } = await createSpreadsheetWithList();
    await openSidePanel(model, env);
    expect(".o_new_list_side_panel").toHaveCount(1);
});

test("Cannot save without model", async function () {
    const { env, model } = await createSpreadsheetWithList();
    await openSidePanel(model, env);
    expect(".primary").toHaveAttribute("disabled");
});

test("Save button is enabled when a model is selected", async function () {
    const { env, model } = await createSpreadsheetWithList();
    await openSidePanel(model, env);
    await contains(".o_model_selector input").click();
    await contains(".o_model_selector_partner").click();
    expect(".primary").not.toHaveAttribute("disabled");
});

test("Create a new list", async function () {
    const { env, model } = await createSpreadsheetWithList();
    const sheetId = model.getters.getActiveSheetId();
    expect(model.getters.getListIds()).toHaveLength(1);
    await openSidePanel(model, env);
    await contains(".o_model_selector input").click();
    await contains(".o_model_selector_partner").click();
    await contains(".o_new_list_side_panel .primary").click();
    expect(model.getters.getListIds()).toHaveLength(2);
    expect(model.getters.getActiveSheetId()).not.toBe(sheetId);
});

test("New list initializes with the correct default configuration", async function () {
    const { env, model } = await createSpreadsheetWithList();
    await openSidePanel(model, env);
    await contains(".o_model_selector input").click();
    await contains(".o_model_selector_partner").click();
    await contains(".o_new_list_side_panel .primary").click();

    const listIds = model.getters.getListIds();
    expect(listIds).toHaveLength(2);
    const listDef = model.getters.getListDefinition(listIds[1]);
    expect(listDef.columns).toEqual([
        { name: "foo", string: "Foo" },
        { name: "bar", string: "Bar" },
        { name: "date", string: "Date" },
        { name: "product_id", string: "Product" },
    ]);
});

test("Fallback to id when no default view exists", async function () {
    const { env, model } = await createSpreadsheetWithList();
    await openSidePanel(model, env);
    await contains(".o_model_selector input").click();
    await contains(".o_model_selector_product").click();
    await contains(".o_new_list_side_panel .primary").click();

    const pivotDef = model.getters.getListDefinition(model.getters.getListIds()[1]);
    expect(pivotDef.columns).toEqual([{ name: "id", string: "ID" }]);
});

test("List insertion inserts 80 records", async () => {
    const serverData = getBasicServerData();
    serverData.models.partner.records = Array.from({ length: 200 }, (_, i) => ({
        foo: i + 1,
        probability: i + 1,
    }));
    const { model, env } = await createSpreadsheetWithList({ serverData });

    await openSidePanel(model, env);
    await contains(".o_model_selector input").click();
    await contains(".o_model_selector_partner").click();
    await contains(".o_new_list_side_panel .primary").click();

    expect(getCellValue(model, "A1")).toBe("Foo");
    const A1 = { col: 0, row: 0, sheetId: model.getters.getActiveSheetId() };
    expect(model.getters.getSpreadZone(A1)).toEqual(toZone("A1:D81"));
});
