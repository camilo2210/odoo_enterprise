import { render } from "@web/owl2/utils";
import { describe, expect, test, getFixture } from "@odoo/hoot";

import { Component, onMounted, onWillUnmount, providePlugins, t, useProps, xml } from "@odoo/owl";
import { stores, owlPlugins } from "@odoo/o-spreadsheet";
import { contains, mountWithCleanup } from "@web/../tests/web_test_helpers";
import { RelatedFilters } from "@spreadsheet_edition/bundle/global_filters/components/related_filters/related_filters";
import { addGlobalFilter } from "@spreadsheet/../tests/helpers/commands";
import { mountSpreadsheet } from "@spreadsheet/../tests/helpers/ui";
import { defineSpreadsheetModels } from "@spreadsheet/../tests/helpers/data";
import { createSpreadsheetWithPivot } from "@spreadsheet/../tests/helpers/pivot";
import { createSpreadsheetWithChart } from "@spreadsheet/../tests/helpers/chart";
import {
    createSpreadsheetWithList,
    insertListInSpreadsheet,
} from "@spreadsheet/../tests/helpers/list";
import { editSelectComponent } from "@spreadsheet_edition/../tests/helpers/webclient_helpers";

const { useStoreProvider, ModelStore } = stores;

defineSpreadsheetModels();
describe.current.tags("desktop");

async function openListSidePanel(listId) {
    await contains(".o-topbar-menu[data-id='data']").click();
    await contains(".o-menu-item[data-name='list_data_sources']").click();
    await contains(`.o-menu-item[data-name='item_list_${listId}']`).click();
}

async function mountSpreadsheetWithListAndOpenSidePanel() {
    const { model } = await createSpreadsheetWithList();
    await mountSpreadsheet(model);
    const [listId] = model.getters.getListIds();
    await openListSidePanel(listId);
}

async function mountSpreadsheetWithPivotAndOpenSidePanel() {
    const { model } = await createSpreadsheetWithPivot();
    await mountSpreadsheet(model);
    await contains(".o-topbar-menu[data-id='data']").click();
    await contains(".o-menu-item[data-name='pivot_data_sources']").click();
    await contains(`.o-menu-item[data-name='item_pivot_1']`).click();
}

async function mountSpreadsheetWithChartAndOpenSidePanel() {
    const { model } = await createSpreadsheetWithChart();
    await mountSpreadsheet(model);
    const [chartId] = model.getters.getChartIds(model.getters.getActiveSheetId());
    await contains(".o-topbar-menu[data-id='data']").click();
    await contains(".o-menu-item[data-name='chart_data_sources']").click();
    await contains(`.o-menu-item[data-name='item_chart_${chartId}']`).click();
}

class Parent extends Component {
    static template = xml`<div class="o-spreadsheet"><RelatedFilters t-props="this.props"/></div>`;
    static components = { RelatedFilters };

    props = useProps({
        resModel: t.string(),
        dataSourceId: t.string(),
        dataSourceType: t.string(),
    });

    setup() {
        providePlugins([owlPlugins.PopoverContainerPlugin], {
            getPopoverContainerRect: () =>
                getFixture().querySelector(".o-spreadsheet").getBoundingClientRect(),
        });
        const stores = useStoreProvider();
        stores.inject(ModelStore, this.env.model);

        onMounted(() => {
            this.env.model.on("update", this, () => render(this, true));
            stores.on("store-updated", this, () => render(this, true));
        });
        onWillUnmount(() => {
            this.env.model.off("update", this);
            stores.off("store-updated", this);
        });
    }
}

async function openSidePanel(model, env, props) {
    await mountWithCleanup(Parent, { env, props });
}

test("can link a new field", async () => {
    const { model, env, pivotId } = await createSpreadsheetWithPivot();
    await addGlobalFilter(model, { id: "43", type: "text", label: "Filter" });
    await openSidePanel(model, env, {
        resModel: "partner",
        dataSourceId: pivotId,
        dataSourceType: "pivot",
    });
    expect(".pivot-dimension").toHaveClass("opacity-50");
    expect(".o_model_field_selector").toHaveCount(0);
    await contains(".o-button-icon[data-icon='link_off']").click();
    await contains(".o_model_field_selector").click();
    await contains(".o_model_field_selector_popover_item_name:first").click();
    expect(model.getters.getPivotFieldMatching(pivotId, "43")).toEqual({
        chain: "display_name",
        type: "char",
    });
});

test("can unlink a field", async () => {
    const { model, env, pivotId } = await createSpreadsheetWithPivot();
    await addGlobalFilter(
        model,
        { id: "43", type: "text", label: "Filter" },
        {
            pivot: {
                [pivotId]: {
                    chain: "display_name",
                    type: "char",
                },
            },
        }
    );
    await openSidePanel(model, env, {
        resModel: "partner",
        dataSourceId: pivotId,
        dataSourceType: "pivot",
    });
    expect(".o_model_field_selector").toHaveText("Display name");
    await contains(".o-button-icon[data-icon='link']").click();
    expect(".pivot-dimension").toHaveClass("opacity-50");
    expect(".o_model_field_selector").toHaveCount(0);
    expect(model.getters.getPivotFieldMatching(pivotId, "43")).toEqual({});
});

test("link a field that have been linked before, restore the previous field matching", async () => {
    const { model, env, pivotId } = await createSpreadsheetWithPivot();
    await addGlobalFilter(
        model,
        { id: "43", type: "text", label: "Filter" },
        {
            pivot: {
                [pivotId]: {
                    chain: "display_name",
                    type: "char",
                },
            },
        }
    );
    await openSidePanel(model, env, {
        resModel: "partner",
        dataSourceId: pivotId,
        dataSourceType: "pivot",
    });
    expect(".o_model_field_selector").toHaveText("Display name");
    await contains(".o-button-icon[data-icon='link']").click();
    expect(model.getters.getPivotFieldMatching(pivotId, "43")).toEqual({});
    await contains(".o-button-icon[data-icon='link_off']").click();
    expect(model.getters.getPivotFieldMatching(pivotId, "43")).toEqual({
        chain: "display_name",
        type: "char",
    });
});

test("can update a field", async () => {
    const { model, env, pivotId } = await createSpreadsheetWithPivot();
    await addGlobalFilter(
        model,
        { id: "43", type: "text", label: "Filter" },
        {
            pivot: {
                [pivotId]: {
                    chain: "name",
                    type: "char",
                },
            },
        }
    );
    await openSidePanel(model, env, {
        resModel: "partner",
        dataSourceId: pivotId,
        dataSourceType: "pivot",
    });
    expect(".o_model_field_selector").toHaveText("name");
    await contains(".o_model_field_selector").click();
    await contains(".o_model_field_selector_popover_item_name:contains(Display name)").click();
    expect(model.getters.getPivotFieldMatching(pivotId, "43")).toEqual({
        chain: "display_name",
        type: "char",
    });
});

test("cannot save a wrong field", async () => {
    const { model, env, pivotId } = await createSpreadsheetWithPivot();
    await addGlobalFilter(model, { id: "43", type: "text", label: "Filter" });
    await openSidePanel(model, env, {
        resModel: "partner",
        dataSourceId: pivotId,
        dataSourceType: "pivot",
    });
    await contains(".o-button-icon[data-icon='link_off']").click();
    await contains(".o_model_field_selector").click();
    // Currency is not a text field
    await contains(".o_model_field_selector_popover_item_name:contains(Currency)").click();
    expect(".pivot-dimension-invalid").toHaveCount(1);
    expect(model.getters.getPivotFieldMatching(pivotId, "43")).toBe(undefined);
});

test("can change date filter offset", async () => {
    const { model, env, pivotId } = await createSpreadsheetWithPivot();
    await addGlobalFilter(
        model,
        { id: "43", type: "date", label: "Filter" },
        {
            pivot: {
                [pivotId]: {
                    chain: "date",
                    type: "date",
                    offset: 0,
                },
            },
        }
    );
    await openSidePanel(model, env, {
        resModel: "partner",
        dataSourceId: pivotId,
        dataSourceType: "pivot",
    });
    expect(".o_model_field_selector").toHaveText("Date");
    expect(".o_filter_field_offset .o-select").toHaveText("No offset");
    await editSelectComponent(".o_filter_field_offset .o-select", "1");
    await contains(".o_filter_offset_input").edit("4");
    expect(model.getters.getPivotFieldMatching(pivotId, "43")).toEqual({
        chain: "date",
        type: "date",
        offset: 4,
    });
});

test("can change list field matching with non-set filter", async () => {
    const { model, env } = await createSpreadsheetWithList();
    await addGlobalFilter(model, {
        id: "42",
        type: "relation",
        label: "Filter",
        modelName: "partner",
    });
    insertListInSpreadsheet(model, {
        model: "partner",
        columns: [
            { name: "foo", string: "Foo" },
            { name: "product_id", string: "Product" },
        ],
    });
    const [list1, list2] = model.getters.getListIds();
    expect(model.getters.getListFieldMatching(list1, "42")).toBe(undefined);
    expect(model.getters.getListFieldMatching(list2, "42")).toBe(undefined);
    await openSidePanel(model, env, {
        resModel: "partner",
        dataSourceId: list1,
        dataSourceType: "list",
    });
    await contains("[data-icon='link_off']").click();
    await contains(".o_model_field_selector").click();
    await contains(".o_model_field_selector_popover_item_name:contains(Id)").click();
    expect(model.getters.getListFieldMatching(list1, "42")).toEqual({
        chain: "id",
        type: "integer",
    });
    expect(model.getters.getListFieldMatching(list2, "42")).toEqual({});
});

describe("global filter creation from list side panel", () => {
    test("select a field with the add button opens the global filter side panel", async () => {
        await mountSpreadsheetWithListAndOpenSidePanel();
        await contains(".add-dimension.o-button:eq(2)").click();
        await contains(
            ".o_popover_field_selector .o_model_field_selector_popover_item[data-name='foo'] button"
        ).click();
        expect(".o_spreadsheet_filter_editor_side_panel").toHaveCount(1);
    });

    test("the global filter has the numeric type if the field is numeric", async () => {
        await mountSpreadsheetWithListAndOpenSidePanel();
        await contains(".add-dimension.o-button:eq(2)").click();
        await contains(
            ".o_popover_field_selector .o_model_field_selector_popover_item[data-name='foo'] button"
        ).click();
        expect(".o_spreadsheet_filter_editor_side_panel").toHaveAttribute(
            "data-id",
            "numeric-filter-panel"
        );
    });

    test("the global filter has the boolean type if the field is boolean", async () => {
        await mountSpreadsheetWithListAndOpenSidePanel();
        await contains(".add-dimension.o-button:eq(2)").click();
        await contains(
            ".o_popover_field_selector .o_model_field_selector_popover_item[data-name='bar'] button"
        ).click();
        expect(".o_spreadsheet_filter_editor_side_panel").toHaveAttribute(
            "data-id",
            "boolean-filter-panel"
        );
    });

    test("the global filter has the date type if the field is date", async () => {
        await mountSpreadsheetWithListAndOpenSidePanel();
        await contains(".add-dimension.o-button:eq(2)").click();
        await contains(
            ".o_popover_field_selector .o_model_field_selector_popover_item[data-name='date'] button"
        ).click();
        expect(".o_spreadsheet_filter_editor_side_panel").toHaveAttribute(
            "data-id",
            "date-filter-panel"
        );
    });

    test("the global filter has the relation type if the field is relation", async () => {
        await mountSpreadsheetWithListAndOpenSidePanel();
        await contains(".add-dimension.o-button:eq(2)").click();
        await contains(
            ".o_popover_field_selector .o_model_field_selector_popover_item[data-name='product_id'] button"
        ).click();
        expect(".o_spreadsheet_filter_editor_side_panel").toHaveAttribute(
            "data-id",
            "relation-filter-panel"
        );
    });

    test("the fields of the global filter are pre-filled", async () => {
        await mountSpreadsheetWithListAndOpenSidePanel();
        await contains(".add-dimension.o-button:eq(2)").click();
        await contains(
            ".o_popover_field_selector .o_model_field_selector_popover_item[data-name='foo'] button"
        ).click();
        expect(".o_global_filter_label").toHaveValue("Foo");
        expect(".o_model_field_selector_value").toHaveText("Foo");
    });

    test("cancelling the creation of a global filter from a list side panel leads back to the list side panel", async () => {
        await mountSpreadsheetWithListAndOpenSidePanel();
        await contains(".add-dimension.o-button:eq(2)").click();
        await contains(
            ".o_popover_field_selector .o_model_field_selector_popover_item[data-name='foo'] button"
        ).click();
        await contains(".o_global_filter_cancel").click();
        expect(".o-listing-details-side-panel").toHaveCount(1);
    });
});

describe("global filter creation from pivot side panel", () => {
    test("select a field with the add button opens the global filter side panel", async () => {
        await mountSpreadsheetWithPivotAndOpenSidePanel();
        await contains(".add-dimension.o-button:eq(3)").click();
        await contains(
            ".o_popover_field_selector .o_model_field_selector_popover_item[data-name='foo'] button"
        ).click();
        expect(".o_spreadsheet_filter_editor_side_panel").toHaveCount(1);
    });

    test("cancelling the creation of a global filter from a pivot side panel leads back to the pivot side panel", async () => {
        await mountSpreadsheetWithPivotAndOpenSidePanel();
        await contains(".add-dimension.o-button:eq(3)").click();
        await contains(
            ".o_popover_field_selector .o_model_field_selector_popover_item[data-name='foo'] button"
        ).click();
        await contains(".o_global_filter_cancel").click();
        expect(".o_spreadsheet_pivot_side_panel").toHaveCount(1);
    });
});

describe("global filter creation from chart side panel", () => {
    test("select a field with the add button opens the global filter side panel", async () => {
        await mountSpreadsheetWithChartAndOpenSidePanel();
        await contains(".add-dimension.o-button").click();
        await contains(
            ".o_popover_field_selector .o_model_field_selector_popover_item[data-name='foo'] button"
        ).click();
        expect(".o_spreadsheet_filter_editor_side_panel").toHaveCount(1);
    });

    test("cancelling the creation of a global filter from a chart side panel leads back to the chart side panel", async () => {
        await mountSpreadsheetWithChartAndOpenSidePanel();
        await contains(".add-dimension.o-button").click();
        await contains(
            ".o_popover_field_selector .o_model_field_selector_popover_item[data-name='foo'] button"
        ).click();
        await contains(".o_global_filter_cancel").click();
        expect(".o-sidePanel .o-sidePanelBody .o-chart").toHaveCount(1);
    });
});
