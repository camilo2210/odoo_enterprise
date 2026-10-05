import { beforeEach, expect, getFixture, test } from "@odoo/hoot";
import { animationFrame, keyDown, keyUp } from "@odoo/hoot-dom";
import { contains, patchWithCleanup, toggleActionMenu } from "@web/../tests/web_test_helpers";
import { Product } from "@spreadsheet/../tests/helpers/data";
import { getCellValue } from "@spreadsheet/../tests/helpers/getters";
import { waitForDataLoaded } from "@spreadsheet/helpers/model";
import { SpreadsheetAction } from "@documents_spreadsheet/bundle/actions/spreadsheet_action";
import { getSpreadsheetActionModel } from "@spreadsheet_edition/../tests/helpers/webclient_helpers";
import { defineDocumentSpreadsheetModels, getBasicData } from "../helpers/data";
import { spawnKanbanViewForSpreadsheet } from "../helpers/kanban_helper";

defineDocumentSpreadsheetModels();

async function selectAllKanbanRecords() {
    const fixture = getFixture();
    await keyDown("alt");
    for (const record of fixture.querySelectorAll(".o_kanban_record:not(.o_kanban_ghost)")) {
        await contains(record).click();
    }
    await keyUp("alt");
}

let spreadsheetAction;
const serverData = {
    models: getBasicData(),
    views: {
        "partner,false,kanban": `
            <kanban>
                <templates>
                    <t t-name="card">
                        <field name="foo"/>
                    </t>
                </templates>
            </kanban>`,
    },
};

beforeEach(() => {
    patchWithCleanup(SpreadsheetAction.prototype, {
        setup() {
            super.setup();
            spreadsheetAction = this;
        },
    });
});

test("Insert in spreadsheet is available on a kanban view", async function () {
    await spawnKanbanViewForSpreadsheet({ serverData });
    await selectAllKanbanRecords();
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

test("Sub-properties are exported from kanban view", async function () {
    const data = getBasicData();
    const charProperty = { type: "char", name: "property_char", string: "Property char" };

    const product = Product._records[0];
    product.properties_definitions = [charProperty];
    data.partner.records = [
        {
            id: 1,
            product_id: product.id,
            partner_properties: {
                [charProperty.name]: "CHAR",
            },
        },
    ];

    await spawnKanbanViewForSpreadsheet({
        serverData: {
            models: data,
            views: {
                "partner,false,kanban": `
                    <kanban>
                        <templates>
                            <t t-name="card">
                                <field name="product_id"/>
                                <field name="partner_properties"/>
                            </t>
                        </templates>
                    </kanban>`,
            },
        },
    });
    await selectAllKanbanRecords();
    await toggleActionMenu();
    await contains(".o-dropdown--menu .o_menu_item:has([data-icon='view_list'])").click();
    await contains(".modal button.btn-primary").click();
    await animationFrame();

    const model = getSpreadsheetActionModel(spreadsheetAction);
    await waitForDataLoaded(model);

    expect(model.getters.getListDefinition("1").columns).toEqual([
        {
            name: "product_id",
            string: "Product",
        },
        {
            name: "partner_properties.property_char",
            string: "Property char",
        },
    ]);
});

test("Insert in spreadsheet is available on a kanban grouped by m2m field", async function () {
    await spawnKanbanViewForSpreadsheet({
        serverData,
        groupBy: ["tag_ids"],
    });
    await selectAllKanbanRecords();
    // Click "Select All" because the "None" group is folded by default
    await contains(".o_control_panel_actions .o_select_domain").click();
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
