import { describe, expect, test } from "@odoo/hoot";
import { waitFor, waitForNone } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import {
    MockServer,
    contains,
    defineModels,
    getService,
    mockService,
    onRpc,
    patchWithCleanup,
    selectFieldDropdownItem,
    serverState,
} from "@web/../tests/web_test_helpers";
import { user } from "@web/core/user";

import {
    DocumentsModels,
    getDocumentsTestServerModelsData,
    makeDocumentRecordData,
} from "./helpers/data";
import { makeDocumentsMockEnv } from "./helpers/model";
import { embeddedActionsServerData } from "./helpers/test_server_data";
import { mountDocumentsListView } from "./helpers/views/list";

describe.current.tags("desktop");

defineModels(DocumentsModels);

/**
 * Shortcut for details panel selector
 * @param selector
 * @return {`.o_documents_details_panel ${string}`}
 */
const dp = (selector) => `.o_documents_details_panel ${selector}`;

test("Open share with view user_permission", async function () {
    const serverData = getDocumentsTestServerModelsData();
    const { id: folder1Id, name: folder1Name } = serverData["documents.document"][0];
    mockService("document.document", {
        openSharingDialog: (documentIds) => {
            expect(documentIds).toEqual([folder1Id]);
            expect.step("open_share");
        },
    });
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsListView();
    await contains(`.o_data_row:contains(${folder1Name}) .o_list_record_selector`).click();
    await contains(".o_control_panel_actions button:contains(Share)").click();

    expect.verifySteps(["open_share"]);
});

test("Right panel shows and updates focused or container record only", async function () {
    const file2Id = 3;
    const serverData = getDocumentsTestServerModelsData([
        makeDocumentRecordData(2, "File 1", { attachment_id: 1, folder_id: 1 }),
        makeDocumentRecordData(file2Id, "File 2", { attachment_id: 2, folder_id: 1 }),
        makeDocumentRecordData(4, "File 3", { attachment_id: 3, folder_id: 1 }),
    ]);
    serverData["ir.attachment"] = [
        { id: 1, name: "One" },
        { id: 2, name: "Two" },
        { id: 3, name: "Three" },
    ];
    const { name: folder1Name } = serverData["documents.document"][0];
    onRpc("web_save", ({ args }) => {
        if (args[0].length === 1 && args[0][0] === file2Id) {
            expect.step("edit_request_2");
        }
    });
    onRpc("ir.model", "display_name_for", ({ args }) =>
        args[0].map((model) => ({ model, display_name: model }))
    );
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsListView();

    // Open right panel
    await contains(".o_control_panel_navigation [data-icon='info']").click();
    await waitFor(".documents_chatter_disabled_overlay");
    // Focus without selection
    await contains(`.o_data_row td[name='name']:contains(${folder1Name})`).click();
    await animationFrame();
    expect(dp(".o_documents_details_panel_name input")).toHaveValue(folder1Name);
    await contains(`.o_list_renderer`).click(); // de-focus

    await waitFor(".documents_chatter_disabled_overlay"); // As we're in all/company
    // Enter folder
    await contains(`.o_data_row:contains(${folder1Name}) [data-icon="folder"]`).click();
    await animationFrame();
    expect(`.o_data_row .o_list_record_selector`).toHaveCount(3);
    expect(dp(".o_documents_details_panel_name input")).toHaveValue(folder1Name);

    // Focus without selection
    await contains(".o_data_row :contains('File 1')").click();
    expect(dp(".o_documents_details_panel_name input")).toHaveValue("File 1");
    // Unfocus
    await contains(`.o_list_renderer`).click();
    expect(dp(".o_documents_details_panel_name input")).toHaveValue(folder1Name);

    // select record focuses it
    await contains(".o_data_row:contains('File 1') .o_list_record_selector").click();
    expect(dp(".o_documents_details_panel_name input")).toHaveValue("File 1");
    // Focus without selection
    await contains(".o_data_row :contains('File 2')").click();
    expect(dp(".o_documents_details_panel_name input")).toHaveValue("File 2");
    // Editing unselected File 2 only
    await contains(dp(".o_documents_details_panel_name input")).edit("File 4");
    // Row is modified, not File 1
    await waitFor(".o_data_row :contains('File 4')");
    await waitFor(".o_data_row :contains('File 1')");

    expect.verifySteps(["edit_request_2"]);
});

test("Document actions are hidden when focused record is not selected", async function () {
    onRpc("ir.model", "display_name_for", ({ args }) =>
        args[0].map((model) => ({ model, display_name: model }))
    );

    const serverData = getDocumentsTestServerModelsData([
        makeDocumentRecordData(2, "File 1", { attachment_id: 1, folder_id: 1 }),
        makeDocumentRecordData(3, "File 2", { attachment_id: 2, folder_id: 1 }),
    ]);
    serverData["ir.attachment"] = [
        { id: 1, name: "One" },
        { id: 2, name: "Two" },
    ];
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsListView();
    // select record focuses it
    await contains(".o_data_row:contains('File 1') .o_list_record_selector").click();
    // Actions are visible as selection is focused
    await waitFor(".o_control_panel_actions:contains('Download')");
    // Focus without selection
    await contains(".o_data_row :contains('File 2')").click();
    await waitFor(".o_selection_container");
    // Actions are no longer visible as focused is not selected
    await waitFor(".o_control_panel_actions:not(:contains('Download'))");
    // Select it to show actions again
    await contains(".o_data_row:contains('File 2') .o_list_record_selector").click();
    await waitFor(".o_control_panel_actions:contains('Download')");
});

test("Actions menu opens after selecting multiple records", async function () {
    const serverData = getDocumentsTestServerModelsData([
        makeDocumentRecordData(2, "File 1", { attachment_id: 1, folder_id: 1 }),
        makeDocumentRecordData(3, "File 2", { attachment_id: 2, folder_id: 1 }),
    ]);
    serverData["ir.attachment"] = [
        { id: 1, name: "One" },
        { id: 2, name: "Two" },
    ];
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsListView();
    await contains(".o_data_row:contains('File 1') .o_list_record_selector").click();
    await contains(".o_data_row:contains('File 2') .o_list_record_selector").click();
    await waitFor(".o_selection_box:contains('2')");
    await contains(".o_cp_action_menus button:contains('Actions')").click();
    await waitFor(".o-dropdown--menu .o_menu_item");
});

test("only show common available actions", async function () {
    await makeDocumentsMockEnv({ serverData: embeddedActionsServerData });
    await mountDocumentsListView();

    await contains(`.o_data_row:contains('Request 1') .o_list_record_selector`).click();
    await waitFor(".o_control_panel_actions:contains('Action 1')");
    await contains(`.o_data_row:contains('Request 1') .o_list_record_selector`).click();

    await contains(`.o_data_row:contains('Request 2') .o_list_record_selector`).click();
    await waitForNone(".o_control_panel_actions:contains('Action 1')");
    await waitFor(".o_control_panel_actions:contains('Action 2 only')");
    await waitFor(".o_control_panel_actions:contains('Action 2 and 3')");

    await contains(`.o_data_row:contains('Request 3') .o_list_record_selector`).click();
    await waitForNone(".o_control_panel_actions:contains('Action 2 only')");
    await waitFor(".o_control_panel_actions:contains('Action 2 and 3')");
});

test("Required document name", async function () {
    const serverData = getDocumentsTestServerModelsData([
        makeDocumentRecordData(2, "Testing file", { folder_id: 1 }),
        makeDocumentRecordData(3, "Testing folder", { folder_id: 1 }),
    ]);
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsListView();
    const lr = (documentName, selector) => `.o_data_row:contains('${documentName}') ${selector}`;
    for (const documentName of ["Testing folder", "Testing file"]) {
        await contains(lr(documentName, ".o_list_record_selector")).click();
        await contains(lr(documentName, ".o_data_cell[name='name']")).click();
        await expect(lr(documentName, ".o_data_cell[name='name'] input")).toHaveCount(1);
        await expect(lr(documentName, ".o_data_cell[name='name'] input")).toHaveValue(documentName);
        // Set empty name
        await contains(lr(documentName, ".o_data_cell[name='name'] input")).edit("");
        await animationFrame();
        expect(".o_notification").toHaveCount(1);
        expect(".o_notification").toHaveText("Name cannot be empty.");
        await contains(".o_notification .o_notification_close").click();
        await expect(lr(documentName, ".o_data_cell[name='name']")).toHaveText(documentName);
        await expect(lr(documentName, ".o_data_cell[name='name'] input")).toHaveCount(0);
        // Remove selection and close record edition
        await contains(".o_list_renderer").click();
        await animationFrame();
    }
});

test("documents list: don't unselect all when interacting with the headers", async () => {
    await makeDocumentsMockEnv({ serverData: embeddedActionsServerData });
    await mountDocumentsListView();

    await contains(".o_data_row:eq(0) .o_list_record_selector input").click();
    await contains(".o_data_row:eq(1) .o_list_record_selector input").click();

    expect(".o_data_row_selected").toHaveCount(2);

    await contains("th:eq(2) .o_resize", { visible: false }).dragAndDrop("th:eq(3)");

    expect(".o_data_row_selected").toHaveCount(2);
});

test("company_id field visibility for internal in multicompany", async function () {
    serverState.companies = [
        { id: 1, name: "Company 1", sequence: 1, parent_id: false, child_ids: [] },
        { id: 2, name: "Company 2", sequence: 2, parent_id: false, child_ids: [] },
    ];
    const serverData = getDocumentsTestServerModelsData();
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsListView({
        context: {
            allowed_company_ids: [1, 2],
        },
    });
    expect("thead th[data-name='company_id']").toHaveCount(1);
});

test("company_id field visibility for portal in multicompany", async function () {
    serverState.companies = [
        { id: 1, name: "Company 1", sequence: 1, parent_id: false, child_ids: [] },
        { id: 2, name: "Company 2", sequence: 2, parent_id: false, child_ids: [] },
    ];
    const testUserGroups = ["base.group_portal", "base.group_multi_company"];
    // We need to do this here and not on the model because has_group("base.group_user")
    // is already in cache before the model method is called the first time.
    patchWithCleanup(user, {
        hasGroup: (group) => testUserGroups.includes(group),
    });
    const serverData = getDocumentsTestServerModelsData();
    const currentUser = serverData["res.users"].find((u) => u.id === serverState.userId);
    // Sync server data for consistency even if it is not really used.
    Object.assign(currentUser, { group_ids: [], share: true });
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsListView({
        context: {
            allowed_company_ids: [1, 2],
        },
    });
    expect("thead th[data-name='company_id']").toHaveCount(0);
});

test("file sharing via link with multiple subfolders", async function () {
    let accessFolder1 = false;
    let accessFolder2 = false;
    let addFolder4 = false;
    onRpc("/documents/touch/accessTokenFolder1", () => {
        expect.step("touch 1");
        accessFolder1 = true;
        return { reload: true };
    });
    onRpc("/documents/touch/accessTokenFolder2", () => {
        expect.step("touch 2");
        accessFolder2 = true;
        return { reload: true };
    });
    onRpc("/documents/touch/accessTokenFolder3", () => ({ reload: true }));
    onRpc("/documents/touch/accessTokenFolder4", () => ({ reload: true }));

    // Set active true/false to control the folders display
    const folder2 = makeDocumentRecordData(2, "Folder 2", {
        type: "folder",
        is_folder: true,
        folder_id: 1,
        access_token: "accessTokenFolder2",
        active: false,
    });
    const folder3 = makeDocumentRecordData(3, "Folder 3", {
        type: "folder",
        is_folder: true,
        folder_id: 2,
        access_token: "accessTokenFolder3",
        active: false,
    });
    const folder4 = makeDocumentRecordData(4, "Folder 4", {
        type: "folder",
        is_folder: true,
        folder_id: 2,
        access_token: "accessTokenFolder4",
        active: false,
    });
    const serverData = getDocumentsTestServerModelsData([folder2, folder3, folder4]);

    await makeDocumentsMockEnv({ serverData });
    const activateFolders = ({ args }) => {
        const DocumentsDocument = MockServer.current.env["documents.document"];
        DocumentsDocument.write(folder2.id, { active: accessFolder1 });
        DocumentsDocument.write(folder3.id, { active: accessFolder2 });
        if (addFolder4) {
            DocumentsDocument.write(folder4.id, { active: accessFolder2 });
            // Ensure only one folder button available
            DocumentsDocument.write(folder3.id, { active: false });
        }
    };
    onRpc("search_panel_select_range", activateFolders);
    onRpc("web_search_read", activateFolders);

    const docService = getService("document.document");
    // Avoid logAccess 1000ms debounce timer
    patchWithCleanup(docService, {
        logAccess: (token) => docService._logAccess(token),
        // Avoid duplicates due to focusRecord logAccess with no debounce
        focusRecord: () => false,
    });
    await mountDocumentsListView();

    await contains(`.o_search_panel_label[data-tooltip="Company"] .o_toggle_fold`).click();
    expect(`.o_data_row .o_field_cell[name="name"]:contains("Folder 1")`).toHaveCount(1);
    await contains(`.o_data_row .o_field_cell .o_field_documents_type_icon`).click();
    expect(`.o_data_row .o_field_cell[name="name"]:contains("Folder 2")`).toHaveCount(1);
    await contains(`.o_data_row .o_field_cell .o_field_documents_type_icon`).click();
    expect(`.o_data_row .o_field_cell[name="name"]:contains("Folder 3")`).toHaveCount(1);
    await contains(`.o_data_row .o_field_cell .o_field_documents_type_icon`).click();

    expect.verifySteps(["touch 1", "touch 2"]);

    expect(`.o_search_panel_label[data-tooltip="Folder 4"]`).toHaveCount(0);
    // New sub-folder added without reloading
    addFolder4 = true;
    await contains(`.o_search_panel_label_title:contains("Folder 2")`).click();
    expect(`.o_search_panel_label[data-tooltip="Folder 4"]`).toHaveCount(0);
    expect(`.o_data_row .o_field_cell[name="name"]:contains("Folder 4")`).toHaveCount(1);
    await contains(`.o_data_row .o_field_cell .o_field_documents_type_icon`).click();
    expect(`.o_search_panel_label[data-tooltip="Folder 4"]`).toHaveCount(1);
    expect.verifySteps(["touch 2"]);
});

test("edit mode is preserved when interacting with modals or control panel", async function () {
    onRpc("/documents/touch/<access_token>", () => ({}));
    const serverData = getDocumentsTestServerModelsData();
    serverData["documents.document"][0].tag_ids = [1, 2];
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsListView();

    // Enter edit mode and open "Search More" modal
    await contains(".o_data_row:nth-child(1) td.o_list_record_selector").click();
    expect(".o_data_row_selected").toHaveCount(1);
    await contains('.o_data_row:nth-child(1) td.o_list_many2one[name="partner_id"]').click();
    await selectFieldDropdownItem("partner_id", "Search more...");
    
    // Clicks inside the modal do not exit edit mode
    await contains(`.modal-title:contains("Search: Contact")`).click();
    await animationFrame();
    expect(".modal-title").toHaveText("Search: Contact");
    expect(".o_data_row_selected").toHaveCount(1);
    await contains(".modal-footer .btn-secondary").click();

    // Clicks inside the row do not exit edit mode (e.g. deleting a tag)
    await contains('.o_data_row:nth-child(1) td[name="tag_ids"]').click();
    await expect('.o_data_row:nth-child(1) .o_field_many2many_tags .o_tag').toHaveCount(2);
    await contains('.o_data_row:nth-child(1) .o_field_many2many_tags .o_delete:eq(0)').click();
    await expect('.o_data_row:nth-child(1) .o_field_many2many_tags .o_tag').toHaveCount(1);

    // Clicks near searchbar exit edit mode
    await contains(".o_control_panel_breadcrumbs").click();
    expect(".o_list_button_discard").toHaveCount(0);
    expect(".o_data_row_selected").toHaveCount(1);

    // Click below the list panel unselects the row
    await contains("div.o_list_renderer.o_documents_view.o_renderer").click();
    expect(".o_data_row_selected").toHaveCount(0);
});
