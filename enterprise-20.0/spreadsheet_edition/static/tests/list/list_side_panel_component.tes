import { describe, expect, getFixture, test } from "@odoo/hoot";
import * as spreadsheet from "@odoo/o-spreadsheet";
import { Component, onMounted, onWillUnmount, t, useProps, xml } from "@odoo/owl";
import { contains, mountWithCleanup } from "@web/../tests/web_test_helpers";
import { createSpreadsheetWithList } from "@spreadsheet/../tests/helpers/list";
import { getActionMenu, mountSpreadsheet } from "@spreadsheet/../tests/helpers/ui";
import { defineSpreadsheetModels } from "@spreadsheet/../tests/helpers/data";
import { animationFrame } from "@odoo/hoot-mock";
import { createSheet, deleteSheet } from "@spreadsheet/../tests/helpers/commands";
import { ListDetailsSidePanel } from "@spreadsheet_edition/bundle/list/side_panels/list_details_side_panel";
import { getFieldItem } from "@spreadsheet_edition/../tests/helpers/webclient_helpers";
import { render } from "@web/owl2/utils";

const { toZone } = spreadsheet.helpers;
const { useStoreProvider, ModelStore } = spreadsheet.stores;

describe.current.tags("desktop");
defineSpreadsheetModels();
const { topbarMenuRegistry } = spreadsheet.registries;

class Parent extends Component {
    static template = xml/* xml */ `
        <div class="o-spreadsheet">
            <ListDetailsSidePanel onCloseSidePanel="() => {}" listId="this.props.listId"/>
        </div>
    `;
    static components = { ListDetailsSidePanel };

    props = useProps({
        model: t.object(),
        listId: t.string(),
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

async function openListSidePanel(model, env, listId) {
    env.notifyUser = env.notifyUser || (() => {});
    env.openSidePanel = env.openSidePanel || (() => {});
    await mountWithCleanup(Parent, {
        env,
        props: { model, listId },
    });
}

describe("list side panel", () => {
    test("Data -> List groups list data sources in a submenu", async () => {
        const { model, env } = await createSpreadsheetWithList();
        const [listId] = model.getters.getListIds();

        const listSubmenu = getActionMenu(topbarMenuRegistry, ["data", "list_data_sources"], env);
        const listAction = getActionMenu(
            topbarMenuRegistry,
            ["data", "list_data_sources", `item_list_${listId}`],
            env
        );

        expect(listSubmenu.name(env).toString()).toBe("List");
        expect(listSubmenu.children(env)).toHaveLength(model.getters.getListIds().length);
        expect(listAction.name(env).toString()).toBe(model.getters.getListDisplayName(listId));
    });

    test("can remove an invalid sorting field", async () => {
        const orderBy = [{ name: "an_invalid_field", asc: true }];
        const { model, env } = await createSpreadsheetWithList({
            model: "partner",
            orderBy,
        });
        const [listId] = model.getters.getListIds();
        expect(model.getters.getListDefinition(listId).orderBy).toEqual(orderBy);
        await openListSidePanel(model, env, listId);
        expect(".o_sorting_rule_column [data-icon='warning']").toHaveCount(1);
        await contains(".o_sorting_rule_column [data-icon='delete']").click();
        expect(model.getters.getListDefinition(listId).orderBy).toEqual([]);
    });

    test("can display a list with invalid fields and delete them", async () => {
        const columns = [
            { name: "name", string: "Name" },
            { name: "foo", string: "Foo" },
        ];
        const badColumns = [
            { name: "name", string: "Name" },
            { name: "an_invalid_field", string: "Invalid Field" },
        ];
        const { model, env } = await createSpreadsheetWithList({
            model: "partner",
            columns,
        });
        const listId = model.getters.getListIds()[0];
        const listDefinition = model.getters.getListDefinition(listId);
        model.dispatch("UPDATE_ODOO_LIST", {
            listId,
            list: {
                ...listDefinition,
                columns: badColumns,
            },
        });
        expect(model.getters.getListDefinition(listId).columns).toEqual(badColumns);
        await openListSidePanel(model, env, listId);
        expect(".pivot-dimension").toHaveCount(2);
        await contains('div[data-id="an_invalid_field"] [data-icon="delete"]').click();
        expect(".pivot-dimension").toHaveCount(1);
        expect(model.getters.getListDefinition(listId).columns).toEqual([
            { name: "name", string: "Name" },
        ]);
    });

    test("can hide/show a field from the side panel", async () => {
        const columns = [
            { name: "name", string: "Name" },
            { name: "foo", string: "Foo" },
        ];
        const { model, env } = await createSpreadsheetWithList({
            model: "partner",
            columns,
            mode: "dynamic",
        });
        const listId = model.getters.getListIds()[0];
        await openListSidePanel(model, env, listId);
        const A1 = { col: 0, row: 0, sheetId: model.getters.getActiveSheetId() };
        expect(model.getters.getSpreadZone(A1)).toEqual(toZone("A1:B5"));
        await contains('div[data-id="foo"] [data-icon="visibility"]').click();
        expect(model.getters.getSpreadZone(A1)).toEqual(toZone("A1:A5"));
        await contains('div[data-id="foo"] [data-icon="visibility_off"]').click();
        expect(model.getters.getSpreadZone(A1)).toEqual(toZone("A1:B5"));
    });

    test("total number of records is fetched and displayed in the side panel", async () => {
        const count = 12000;
        const { model, env } = await createSpreadsheetWithList({
            mockRPC: async function (route, args) {
                if (args.method === "search_count" && args.model === "partner") {
                    return args.kwargs?.limit ?? count;
                }
            },
            model: "partner",
            columns: [{ name: "name", string: "Name" }],
        });
        const listId = model.getters.getListIds()[0];
        const parent = await mountWithCleanup(Parent, {
            env,
            props: { model, listId },
        });
        // `ListDetailsSidePanel` only fetches the records count in `onWillUpdateProps`,
        // which Owl doesn't call on the initial mount. Force one re-render, as a real
        render(parent, true);
        await animationFrame();
        expect(".o-section:has(.o_model_name) span").toHaveText("10000+ records");
        await contains(".o-section:has(.o_model_name) span").click();
        await animationFrame();
        expect(".o-section:has(.o_model_name) span").toHaveText(`${count} records`);
    });

    test("columns without an explicit header display the field label in side panel", async () => {
        const { model, env } = await createSpreadsheetWithList({
            model: "partner",
            columns: [{ name: "foo" }],
        });
        const [listId] = model.getters.getListIds();
        await openListSidePanel(model, env, listId);

        expect(".pivot-dimension input.os-input").toHaveValue("Foo");
        expect(model.getters.getListDefinition(listId).columns).toEqual([{ name: "foo" }]);
    });

    test("can set a custom list column header directly from the side panel", async () => {
        const { model, env } = await createSpreadsheetWithList({
            model: "partner",
            columns: [{ name: "foo" }],
        });
        const [listId] = model.getters.getListIds();
        await openListSidePanel(model, env, listId);

        await contains(".pivot-dimension input.os-input").click();
        await contains(".pivot-dimension input.os-input").edit("My Header");
        await animationFrame();

        expect(model.getters.getListDefinition(listId).columns).toEqual([
            { name: "foo", string: "My Header" },
        ]);
    });

    test("date field is filtered out of the popup once added as a column", async function () {
        const { model, env } = await createSpreadsheetWithList({
            model: "partner",
            columns: [{ name: "foo" }],
        });
        const [listId] = model.getters.getListIds();
        await openListSidePanel(model, env, listId);
        const fixture = getFixture();

        await contains(".add-dimension.o-button").click();
        expect(getFieldItem("date", fixture)).not.toBe(null);
        getFieldItem("date", fixture).querySelector("button").click();
        await animationFrame();

        await contains(".add-dimension.o-button").click();
        expect(getFieldItem("date", fixture)).toBe(null);
    });
});

test("Can remove an unused list in the data source cleanup side panel", async () => {
    const { model } = await createSpreadsheetWithList({});
    const [listId] = model.getters.getListIds();
    createSheet(model, { sheetId: "sh2" });
    deleteSheet(model, model.getters.getActiveSheetId());
    expect(model.getters.isListUnused(listId)).toBe(true);

    await mountSpreadsheet(model);
    await contains(".o-topbar-menu[data-id='data']").click();
    await contains(".o-menu-item[data-name='data_cleanup']").click();
    await contains(".o-menu-item[data-name='data_sources_cleanup']").click();

    expect(`.o-sidePanel input[name="${listId}"]`).toBeChecked();

    await contains(".o-sidePanel button").click();
    expect(`.o-sidePanel input[name="${listId}"]`).toHaveCount(0);
    expect(model.getters.getListIds()).toEqual([]);
});
