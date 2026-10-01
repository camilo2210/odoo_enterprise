import { basicDocumentsListArch } from "@documents/../tests/helpers/views/list";
import { defineDocumentSpreadsheetModels } from "@documents_spreadsheet/../tests/helpers/data";
import { makeDocumentsSpreadsheetMockEnv } from "@documents_spreadsheet/../tests/helpers/model";
import { mockActionService } from "@documents_spreadsheet/../tests/helpers/spreadsheet_test_utils";
import { expect, test } from "@odoo/hoot";
import { contains, mountView } from "@web/../tests/web_test_helpers";
import { getEnrichedSearchArch } from "@documents/../tests/helpers/views/search";
import { getDocumentsTestServerModelsData } from "@documents/../tests/helpers/data";
import { browser } from "@web/core/browser/browser";

defineDocumentSpreadsheetModels();

async function mountListView() {
    await mountView({
        type: "list",
        resModel: "documents.document",
        arch: basicDocumentsListArch,
        searchViewArch: getEnrichedSearchArch(),
    });
}

test("opening csv triggers conversion dialog", async function () {
    const spreadsheetId = 2;
    const documentModels = getDocumentsTestServerModelsData([
        {
            id: spreadsheetId,
            name: "My CSV file",
            thumbnail_status: "present",
            attachment_id: 1, // Necessary to not be considered as a request
        },
    ]);
    documentModels["ir.attachment"] = [{ id: 1, mimetype: "text/csv" }];
    await makeDocumentsSpreadsheetMockEnv({
        serverData: {
            models: Object.fromEntries(
                Object.entries(documentModels).map(([name, records]) => [name, { records }])
            ),
        },
    });
    mockActionService((action, options) => {
        expect.step(action);
        expect(options.additionalContext.default_document_id).toEqual(spreadsheetId);
    });
    await mountListView();
    await contains(
        ".o_data_row:contains('My CSV file') .o_field_cell .o_field_documents_type_icon"
    ).click();
    expect.verifySteps(["documents_spreadsheet.import_to_spreadsheet_action"]);
});

test("opening trashed csv prompts restore dialog and restores file on confirm", async () => {
    const spreadsheetId = 2;
    const documentModels = getDocumentsTestServerModelsData([
        {
            id: spreadsheetId,
            name: "Trashed CSV file",
            thumbnail_status: "present",
            active: false,
            attachment_id: 1, // Necessary to not be considered as a request
        },
    ]);
    documentModels["ir.attachment"] = [{ id: 1, mimetype: "text/csv" }];
    await makeDocumentsSpreadsheetMockEnv({
        serverData: {
            models: Object.fromEntries(
                Object.entries(documentModels).map(([name, records]) => [name, { records }])
            ),
        },
        mockRPC: async (route, args) => {
            if (args.method === "action_unarchive") {
                expect.step("spreadsheet_restored");
                expect(args.model).toBe("documents.document");
                expect(args.args).toEqual([spreadsheetId]);
            }
            return null;
        },
    });

    // Set the document folder in localStorage to "TRASH" so the trash view opens by default
    browser.localStorage.setItem("searchpanel_documents_document", "TRASH");

    await mountListView();
    await contains(
        ".o_data_row:contains('Trashed CSV file') .o_field_cell .o_field_documents_type_icon"
    ).click();
    await contains(".modal-content .btn.btn-primary:contains('Restore')").click();
    expect.verifySteps(["spreadsheet_restored"]);
});
