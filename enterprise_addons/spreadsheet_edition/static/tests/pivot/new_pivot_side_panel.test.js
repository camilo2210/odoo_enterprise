import { render } from "@web/owl2/utils";
import { defineSpreadsheetModels, getBasicServerData } from "@spreadsheet/../tests/helpers/data";
import { describe, expect, test } from "@odoo/hoot";
import { stores } from "@odoo/o-spreadsheet";
import { createSpreadsheetWithPivot } from "@spreadsheet/../tests/helpers/pivot";
import { contains, mountWithCleanup } from "@web/../tests/web_test_helpers";
import { Component, onMounted, onWillUnmount, t, useProps, xml } from "@odoo/owl";
import { NewPivotSidePanel } from "@spreadsheet_edition/bundle/pivot/side_panels/new_pivot_side_panel/new_pivot_side_panel";
import { getCellValue } from "@spreadsheet/../tests/helpers/getters";
const { useStoreProvider, ModelStore } = stores;

defineSpreadsheetModels();
describe.current.tags("desktop");

class Parent extends Component {
    static template = xml/* xml */ `
        <NewPivotSidePanel onCloseSidePanel="() => {}"/>
    `;
    static components = { NewPivotSidePanel };

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

test("Open new pivot side panel", async function () {
    const { env, model } = await createSpreadsheetWithPivot();
    await openSidePanel(model, env);
    expect(".o_new_pivot_side_panel").toHaveCount(1);
});

test("Cannot save without model", async function () {
    const { env, model } = await createSpreadsheetWithPivot();
    await openSidePanel(model, env);
    expect(".primary").toHaveAttribute("disabled");
});

test("Save button is enabled when a model is selected", async function () {
    const { env, model } = await createSpreadsheetWithPivot();
    await openSidePanel(model, env);
    await contains(".o_model_selector input").click();
    await contains(".o_model_selector_partner").click();
    expect(".primary").not.toHaveAttribute("disabled");
});

test("Create a new pivot", async function () {
    const { env, model } = await createSpreadsheetWithPivot();
    const sheetId = model.getters.getActiveSheetId();
    expect(model.getters.getPivotIds()).toHaveLength(1);
    await openSidePanel(model, env);
    await contains(".o_model_selector input").click();
    await contains(".o_model_selector_partner").click();
    await contains(".o_new_pivot_side_panel .primary").click();
    expect(model.getters.getPivotIds()).toHaveLength(2);
    expect(model.getters.getActiveSheetId()).not.toBe(sheetId);
});

test("New pivot initializes with the correct default configuration", async function () {
    const { env, model } = await createSpreadsheetWithPivot();
    await openSidePanel(model, env);
    await contains(".o_model_selector input").click();
    await contains(".o_model_selector_partner").click();
    await contains(".o_new_pivot_side_panel .primary").click();

    const pivotIds = model.getters.getPivotIds();
    expect(pivotIds).toHaveLength(2);
    const pivotDef = model.getters.getPivotCoreDefinition(pivotIds[1]);
    expect(pivotDef.rows).toEqual([{ fieldName: "bar" }]);
    expect(pivotDef.columns).toEqual([{ fieldName: "foo" }]);
    expect(pivotDef.measures).toEqual([
        { id: "probability:avg", fieldName: "probability", aggregator: "avg" },
    ]);
});

test("Fallback to __count measure when no default measure exists", async function () {
    const { env, model } = await createSpreadsheetWithPivot();
    await openSidePanel(model, env);
    await contains(".o_model_selector input").click();
    await contains(".o_model_selector_product").click();
    await contains(".o_new_pivot_side_panel .primary").click();

    const pivotDef = model.getters.getPivotCoreDefinition(model.getters.getPivotIds()[1]);
    expect(pivotDef.rows).toEqual([]);
    expect(pivotDef.columns).toEqual([]);
    expect(pivotDef.measures).toEqual([
        { id: "__count:count", fieldName: "__count", aggregator: "count" },
    ]);
});

test("Pivot insertion auto-expands sheet when columns exceed default no of columns", async () => {
    const serverData = getBasicServerData();
    serverData.models.partner.records = Array.from({ length: 30 }, (_, i) => ({
        foo: i + 1,
        probability: i + 1,
    }));
    const { model, env } = await createSpreadsheetWithPivot({ serverData });
    const sheetId = model.getters.getActiveSheetId();
    const defaultNoOfColumns = model.getters.getSheet(sheetId).numberOfCols;

    await openSidePanel(model, env);
    await contains(".o_model_selector input").click();
    await contains(".o_model_selector_partner").click();
    await contains(".o_new_pivot_side_panel .primary").click();

    const newSheetId = model.getters.getActiveSheetId();
    expect(getCellValue(model, "A1")).toBe("Partner");
    expect(model.getters.getSheet(newSheetId).numberOfCols).toBeGreaterThan(defaultNoOfColumns);
});
