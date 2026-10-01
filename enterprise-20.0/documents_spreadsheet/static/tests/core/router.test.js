import { describe, expect, test } from "@odoo/hoot";
import { router } from "@web/core/browser/router";

describe.current.tags("headless");

const urlToState = (url) => router.urlToState(new URL(url, "https://www.hoot.test"));

describe("documents spreadsheet router", () => {
    test("replaces the spreadsheet id with the access token", () => {
        expect(
            router.stateToUrl({
                access_token: "token with/slashof",
                action: "spreadsheet",
                resId: 15,
                sid: "sheet1",
            })
        ).toBe("/odoo/spreadsheet/token%20with%2Fslashof?sid=sheet1");
    });

    test("keeps the existing action path before the spreadsheet action", () => {
        expect(
            router.stateToUrl({
                access_token: "spreadsheetTokeno25",
                action: "spreadsheet",
                actionStack: [
                    { action: "surveys", resId: 2 },
                    { active_id: 2, action: "spreadsheet", resId: 37 },
                ],
                resId: 37,
                sid: "sheet1",
            })
        ).toBe("/odoo/surveys/2/spreadsheet/spreadsheetTokeno25?sid=sheet1");
    });

    test("keeps the regular documents access token URL", () => {
        expect(
            router.stateToUrl({
                access_token: "documentToken",
                action: "documents",
            })
        ).toBe("/odoo/documents/documentToken");
    });

    test("reads spreadsheet access token from the URL", () => {
        expect(
            urlToState("/odoo/surveys/2/spreadsheet/spreadsheetTokeno25?sid=sheet1")
        ).toMatchObject({
            access_token: "spreadsheetTokeno25",
            action: "spreadsheet",
            resId: 37,
            sid: "sheet1",
        });
    });
});
