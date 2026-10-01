import { expect, test, describe } from "@odoo/hoot";
import { setCellContent } from "@spreadsheet/../tests/helpers/commands";
import { getEvaluatedCell } from "@spreadsheet/../tests/helpers/getters";
import { defineTestSpreadsheetEditionModels } from "@test_spreadsheet_edition/../tests/helpers/data";
import { createSpreadsheetTestAction } from "@test_spreadsheet_edition/../tests/helpers/helpers";
import { contains } from "@web/../tests/web_test_helpers";

defineTestSpreadsheetEditionModels();
describe.current.tags("desktop");

test("Opening the composer on a date cell opens a date picker popover", async function () {
    const { model } = await createSpreadsheetTestAction("spreadsheet_test_action");
    expect(".o_popover .o_datetime_picker").toHaveCount(0);
    setCellContent(model, "A1", "1900-01-15");
    await contains(".o-topbar-composer .o-composer").click();

    expect(".o_popover .o_datetime_picker").toHaveCount(1);
    expect(".o_datetime_picker_header .o_datetime_button").toHaveText("Jan 1900");
    expect(".o_date_item_cell.o_selected").toHaveText("15");

    await contains(".o_date_item_cell", { text: "4" }).click();

    expect(getEvaluatedCell(model, "A1").value).toBe(5); // 1900-01-04 is 5 days since 1899-12-30
    expect(getEvaluatedCell(model, "A1").format).toBe("yyyy-mm-dd"); // Format is preserved
});

test("Opening a composer on a cell with a formula does not open date picker", async function () {
    const { model } = await createSpreadsheetTestAction("spreadsheet_test_action");
    setCellContent(model, "A1", "=TODAY()");
    await contains(".o-topbar-composer .o-composer").click();
    expect(".o_popover .o_datetime_picker").toHaveCount(0);
});

test("Clicking on the date picker doesn't blur the composer", async function () {
    const { model } = await createSpreadsheetTestAction("spreadsheet_test_action");
    setCellContent(model, "A1", "1900-01-15");
    await contains(".o-topbar-composer .o-composer").click();
    expect(document.activeElement).toHaveClass("o-composer");

    await contains(".o_popover .o_datetime_picker").click();
    expect(document.activeElement).toHaveClass("o-composer");
});
