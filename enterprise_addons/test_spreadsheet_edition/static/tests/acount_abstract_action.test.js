import { expect, test } from "@odoo/hoot";
import { defineTestSpreadsheetEditionModels } from "@test_spreadsheet_edition/../tests/helpers/data";
import { createSpreadsheetTestAction } from "@test_spreadsheet_edition/../tests/helpers/helpers";
import { onRpc } from "@web/../tests/web_test_helpers";

defineTestSpreadsheetEditionModels();

test.tags("desktop");
test("Fiscal year getters are defined in the model", async () => {
    onRpc(
        "/spreadsheet/data/spreadsheet.test/1",
        () => {
            const response = {
                data: {},
                name: "Spreadsheet Test 1",
                revisions: [],
                current_fiscal_year_start: "2025-10-01",
                current_fiscal_year_end: "2026-09-30",
            };
            return new Response(JSON.stringify(response));
        },
        { pure: true }
    );
    const { model } = await createSpreadsheetTestAction("spreadsheet_test_action");
    expect(model.getters.getCurrentFiscalYearStart().toISODate()).toEqual("2025-10-01");
    expect(model.getters.getCurrentFiscalYearEnd().toISODate()).toEqual("2026-09-30");
});
