import {
    contains,
    mountView,
    patchWithCleanup,
    toggleActionMenu,
} from "@web/../tests/web_test_helpers";
import { expect, test } from "@odoo/hoot";
import { session } from "@web/session";
import { defineSpreadsheetModels } from "@spreadsheet/../tests/helpers/data";
import { keyDown, keyUp } from "@odoo/hoot-dom";

defineSpreadsheetModels();

async function openKanbanActionMenu() {
    await mountView({
        type: "kanban",
        resModel: "partner",
        arch: `
            <kanban>
                <templates>
                    <t t-name="card">
                        <field name="foo"/>
                    </t>
                </templates>
            </kanban>`,
        actionMenus: {},
    });
    await keyDown("alt");
    await contains(".o_kanban_record").click();
    await keyUp("alt");
    await toggleActionMenu();
}

test("Insert in Spreadsheet is available when the user have permission", async function () {
    await openKanbanActionMenu();
    expect(".o-dropdown--menu .o_menu_item:has([data-icon='view_list'])").toHaveCount(1);
});

test("Insert in Spreadsheet is unavailable when the user lacks permission", async function () {
    patchWithCleanup(session, { can_insert_in_spreadsheet: false });
    await openKanbanActionMenu();
    expect(".o-dropdown--menu .o_menu_item:has([data-icon='view_list'])").toHaveCount(0);
});
