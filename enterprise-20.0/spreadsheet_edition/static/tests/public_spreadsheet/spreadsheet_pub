import { beforeEach, describe, expect, getFixture, mockFetch, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { mockService, mountWithCleanup } from "@web/../tests/web_test_helpers";
import { location } from "@web/core/browser/browser";

import { defineSpreadsheetModels } from "@spreadsheet/../tests/helpers/data";
import { createModelWithDataSource } from "@spreadsheet/../tests/helpers/model";
import { freezeOdooData } from "@spreadsheet/helpers/model";

import { setCellContent } from "@spreadsheet/../tests/helpers/commands";
import { makeFakeSpreadsheetService } from "@spreadsheet_edition/../tests/helpers/collaborative_helpers";
import { PublicSpreadsheet } from "@spreadsheet_edition/public_spreadsheet/public_spreadsheet";

defineSpreadsheetModels();

let data = {};

async function mountPublicSpreadsheet() {
    mockService("spreadsheet_collaborative", makeFakeSpreadsheetService());
    mockFetch(() => ({ data, revisions: [] }));
    const component = await mountWithCleanup(PublicSpreadsheet, {
        props: {
            dataUrl: "/dataUrl",
            resModel: "partner",
            resId: 1,
            accessToken: "access-token",
            mode: "normal",
        },
    });
    await animationFrame();
    return {
        fixture: getFixture(),
        model: component.model,
    };
}

function getHashParam(key) {
    return new URLSearchParams(location.hash.slice(1)).get(key);
}

test("mounts and renders the spreadsheet grid", async () => {
    const { model } = await createModelWithDataSource();
    const data = await freezeOdooData(model);
    const { fixture } = await mountPublicSpreadsheet(data);
    expect(fixture.querySelector(".o-spreadsheet")).toBeVisible();
});

test("Internal links converted to neutralized are not clickable", async function (assert) {
    const { model } = await createModelWithDataSource();
    setCellContent(model, "A1", "[label](odoo://ir_menu_xml_id/test_menu)");
    data = await freezeOdooData(model);
    const { fixture } = await mountPublicSpreadsheet(data);
    expect(fixture.querySelector(".o-dashboard-clickable-cell")).toBe(null);
});

describe("sid URL synchronization", () => {
    beforeEach(async () => {
        const { model } = await createModelWithDataSource({
            spreadsheetData: {
                sheets: [
                    { id: "sheet1", name: "Sheet1" },
                    { id: "sheet2", name: "Sheet2" },
                ],
            },
        });
        data = await freezeOdooData(model);
    });

    test("activates sheet from URL on initialization", async () => {
        location.hash = "#sid=sheet2";
        const { model } = await mountPublicSpreadsheet();
        expect(model.getters.getActiveSheetId()).toBe("sheet2");
    });

    test("falls back to the first sheet and syncs the URL when sid is invalid", async () => {
        location.hash = "#sid=unknown";
        const { model } = await mountPublicSpreadsheet();
        expect(getHashParam("sid")).toBe("sheet1");
        expect(model.getters.getActiveSheetId()).toBe("sheet1");
    });

    test("falls back to the first sheet and syncs the URL when sid is absent", async () => {
        const { model } = await mountPublicSpreadsheet();
        expect(model.getters.getActiveSheetId()).toBe("sheet1");
        expect(getHashParam("sid")).toBe("sheet1");
    });

    test("syncs the URL when the active sheet changes", async () => {
        const { model } = await mountPublicSpreadsheet();
        model.dispatch("ACTIVATE_SHEET", {
            sheetIdFrom: "sheet1",
            sheetIdTo: "sheet2",
        });
        expect(getHashParam("sid")).toBe("sheet2");
    });
});
