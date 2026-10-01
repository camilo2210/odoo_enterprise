import {
    defineDocumentSpreadsheetModels,
    getBasicServerData,
} from "@documents_spreadsheet/../tests/helpers/data";
import { createSpreadsheet } from "@documents_spreadsheet/../tests/helpers/spreadsheet_test_utils";
import { contains } from "@web/../tests/web_test_helpers";
import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { mockActionService } from "../../helpers/spreadsheet_test_utils";

defineDocumentSpreadsheetModels();
describe.current.tags("desktop");

const spreadsheetId = 42;
const serverData = getBasicServerData();
beforeEach(() => {
    serverData.models["documents.document"].records = [
        {
            id: spreadsheetId,
            name: "Trash Test Sheet",
            spreadsheet_data: "{}",
            active: false,
        },
    ];
});

test("shows trash banner and open in readonly mode when spreadsheet is in trash", async () => {
    const { env } = await createSpreadsheet({
        spreadsheetId,
        serverData,
    });
    expect(".trash-banner").toHaveCount(1);
    expect(env.model.getters.isReadonly()).toBe(true);
});

test("click on take out of trash should call action_archive and reload the context", async () => {
    await createSpreadsheet({
        spreadsheetId,
        serverData,
        mockRPC: async function (route, args) {
            if (args.method === "action_unarchive" && args.model === "documents.document") {
                expect.step("action_unarchive");
            }
        },
    });
    mockActionService((action) => {
        expect.step(action);
    });
    await contains(".trash-banner .btn.btn-link").click();
    expect.verifySteps(["action_unarchive", "reload_context"]);
});
