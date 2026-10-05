import { describe, expect, test } from "@odoo/hoot";
import { contains } from "@web/../tests/web_test_helpers";
import { createSpreadsheetWithList } from "@spreadsheet/../tests/helpers/list";
import { mountSpreadsheet } from "@spreadsheet/../tests/helpers/ui";
import { defineSpreadsheetModels } from "@spreadsheet/../tests/helpers/data";

describe.current.tags("desktop");
defineSpreadsheetModels();

async function openListSidePanel(listId) {
    await contains(".o-topbar-menu[data-id='data']").click();
    await contains(".o-menu-item[data-name='list_data_sources']").click();
    await contains(`.o-menu-item[data-name='item_list_${listId}']`).click();
}

async function openAddColumnPopover() {
    await contains(".add-dimension").click();
}

describe("list calculated column", () => {
    test("can add a calculated column via the side panel with unique names", async () => {
        const { model } = await createSpreadsheetWithList({
            model: "partner",
            columns: [{ name: "name", string: "Name" }],
        });
        await mountSpreadsheet(model);
        const [listId] = model.getters.getListIds();
        await openListSidePanel(listId);
        expect(".pivot-dimension").toHaveCount(1);

        await openAddColumnPopover();
        await contains(".btn:contains('Add Calculated Column')").click();

        let columns = model.getters.getListDefinition(listId).columns;
        expect(columns).toHaveLength(2);
        expect(columns[1].string).toBe("New calculated column");
        expect(columns[1].computedBy.formula).toBe("=0");
        expect(".pivot-dimension").toHaveCount(2);

        await openAddColumnPopover();
        await contains(".btn:contains('Add Calculated Column')").click();

        columns = model.getters.getListDefinition(listId).columns;
        expect(columns).toHaveLength(3);
        const calculatedColumns = columns.filter((col) => col.computedBy);
        expect(calculatedColumns[0].name).not.toBe(calculatedColumns[1].name);
    });

    test("calculated column is added with hidden=false and reference the active sheet", async () => {
        const { model } = await createSpreadsheetWithList({
            model: "partner",
            columns: [{ name: "name", string: "Name" }],
        });
        await mountSpreadsheet(model);
        const [listId] = model.getters.getListIds();
        const activeSheetId = model.getters.getActiveSheetId();
        await openListSidePanel(listId);

        await openAddColumnPopover();
        await contains(".btn:contains('Add Calculated Column')").click();

        const columns = model.getters.getListDefinition(listId).columns;
        const calculatedColumn = columns.find((col) => col.computedBy);
        expect(calculatedColumn.hidden).toBe(false);
        expect(calculatedColumn.computedBy.sheetId).toBe(activeSheetId);
    });

    test("can rename a calculated column", async () => {
        const { model } = await createSpreadsheetWithList({
            columns: [{ name: "foo", string: "Foo" }],
            linesNumber: 1,
        });
        await mountSpreadsheet(model);
        const [listId] = model.getters.getListIds();
        const sheetId = model.getters.getActiveSheetId();

        // Set up two calculated columns where col2's formula references col1 by name
        const listDef = model.getters.getListDefinition(listId);
        model.dispatch("UPDATE_ODOO_LIST", {
            listId,
            list: {
                ...listDef,
                columns: [
                    {
                        name: "ALALA",
                        string: "ALALA",
                        computedBy: { sheetId, formula: "=0" },
                        hidden: false,
                    },
                    {
                        name: "BABABA",
                        string: "BABABA",
                        computedBy: { sheetId, formula: "=ALALA" },
                        hidden: false,
                    },
                    ...listDef.columns,
                ],
            },
        });

        await openListSidePanel(listId);

        // Rename col1 via the side panel input
        await contains(".pivot-dimension input").click();
        await contains(".pivot-dimension input").edit("MyColumn");

        const columns = model.getters.getListDefinition(listId).columns;
        const renamedCol = columns.find((col) => col.string === "MyColumn");
        const col2 = columns.find((col) => col.string === "BABABA");

        expect(renamedCol.string).toBe("MyColumn");
        expect(renamedCol.name).toBe("MyColumn");
        expect(col2.computedBy.formula).toBe("=MyColumn");
    });
});
