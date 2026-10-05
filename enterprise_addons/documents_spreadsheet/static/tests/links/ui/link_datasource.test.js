import { defineDocumentSpreadsheetModels } from "@documents_spreadsheet/../tests/helpers/data";
import { beforeEach, describe, expect, getFixture, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { press } from "@odoo/hoot-dom";
import { components, registries } from "@odoo/o-spreadsheet";
import { setCellContent } from "@spreadsheet/../tests/helpers/commands";
import { contains, mockService, patchWithCleanup } from "@web/../tests/web_test_helpers";
import { createSpreadsheetFromPivotView } from "../../helpers/pivot_helpers";
import { insertListInSpreadsheet } from "@spreadsheet/../tests/helpers/list";

describe.current.tags("desktop");
defineDocumentSpreadsheetModels();

const { cellMenuRegistry } = registries;
const { Grid } = components;

let target;

function labelInput() {
    return target.querySelectorAll(".o-link-editor input")[0];
}

function urlInput() {
    return target.querySelector(".o-link-editor .o-link-url input");
}

beforeEach(() => {
    target = getFixture();
    patchWithCleanup(Grid.prototype, {
        setup() {
            super.setup();
            this.hoveredCell.hover({ col: 0, row: 0 });
        },
    });
});

async function openLinkEditor(env) {
    const insertLinkMenu = cellMenuRegistry.getAll().find((item) => item.id === "insert_link");
    await insertLinkMenu.execute(env);
    await animationFrame();
}

test("insert a datasource link", async () => {
    const { model, env } = await createSpreadsheetFromPivotView();
    insertListInSpreadsheet(model, {
        sheetId: model.getters.getActiveSheetId(),
        model: "product",
        columns: [
            { name: "name", string: "Name" },
            { name: "active", string: "Active" },
        ],
        name: "Partner",
    });
    const activeSheetId = model.getters.getActiveSheetId();
    model.dispatch("RENAME_SHEET", {
        sheetId: activeSheetId,
        oldName: model.getters.getSheetName(activeSheetId),
        newName: "no match",
    });
    await openLinkEditor(env);
    await contains(urlInput()).edit("Partner", { confirm: false });
    await press("arrowDown");
    await press("Enter");
    await animationFrame();
    expect(labelInput()).toHaveValue("Pivot #1 - Partners by Foo", {
        message: "The label should be the menu name",
    });
    await press("arrowDown");
    await press("Enter");
    await animationFrame();
    expect(labelInput()).toHaveValue("List #1 - Partner", {
        message: "The label should be the menu name",
    });
});

test("follow a datasource link", async () => {
    const { model, pivotId } = await createSpreadsheetFromPivotView();
    setCellContent(model, "A1", `[Pivot](odoo-data-source://pivot/${pivotId})`);
    mockService("action", {
        doAction(action) {
            expect.step("do-action");
            expect(action.type).toBe("ir.actions.act_window");
            expect(action.res_model).toBe("partner");
            expect(action.target).toBe("current");
        },
    });
    await animationFrame();
    const link = document.querySelector("a.o-link");
    await contains(link).click();
    expect.verifySteps(["do-action"]);
});
