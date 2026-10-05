import { defineDocumentSpreadsheetModels } from "@documents_spreadsheet/../tests/helpers/data";
import { createSpreadsheet } from "@documents_spreadsheet/../tests/helpers/spreadsheet_test_utils";
import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { components } from "@odoo/o-spreadsheet";
import { setCellContent, setSelection } from "@spreadsheet/../tests/helpers/commands";
import { getMenuServerData } from "@documents_spreadsheet/../tests/links/menu_data_utils";
import { contains, patchWithCleanup } from "@web/../tests/web_test_helpers";

describe.current.tags("desktop");
defineDocumentSpreadsheetModels();

const { Grid } = components;

beforeEach(() => {
    patchWithCleanup(Grid.prototype, {
        setup() {
            super.setup();
            this.hoveredCell.hover({ col: 0, row: 0 });
        },
    });
});

test("ir.menu link keep breadcrumb", async function () {
    const { model } = await createSpreadsheet({
        serverData: getMenuServerData(),
    });
    setCellContent(model, "A1", "[menu with xmlid](odoo://ir_menu_xml_id/test_menu)");
    setSelection(model, "A1");
    await animationFrame();
    const link = document.querySelector("a.o-link");
    await contains(link).click();
    expect(".o_breadcrumb").toHaveText("Untitled spreadsheet\naction1");
});
