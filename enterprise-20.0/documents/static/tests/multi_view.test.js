import { animationFrame, describe, expect, rightClick, test } from "@odoo/hoot";
import { waitFor, waitForNone } from "@odoo/hoot-dom";
import { inputFiles } from "@mail/../tests/mail_test_helpers";
import {
    contains,
    defineActions,
    defineModels,
    getService,
    mockService,
    mountWithCleanup,
    onRpc,
} from "@web/../tests/web_test_helpers";
import { WebClient } from "@web/webclient/webclient";
import {
    DocumentsModels,
    getDocumentsTestServerModelsData,
    makeDocumentRecordData,
} from "@documents/../tests/helpers/data";
import { makeDocumentsMockEnv } from "@documents/../tests/helpers/model";
import { embeddedActionsServerData } from "@documents/../tests/helpers/test_server_data";
import { basicDocumentsActivityArch } from "@documents/../tests/helpers/views/activity";
import { basicDocumentsKanbanArch } from "@documents/../tests/helpers/views/kanban";
import { basicDocumentsListArch } from "@documents/../tests/helpers/views/list";
import { getEnrichedSearchArch } from "@documents/../tests/helpers/views/search";
import { EventBus } from "@odoo/owl";

defineModels(DocumentsModels);
defineActions([
    {
        id: 1,
        name: "Documents",
        res_model: "documents.document",
        views: [
            [false, "kanban"],
            [false, "list"],
            [false, "activity"],
        ],
    },
    {
        id: 2,
        name: "Documents All",
        res_model: "documents.document",
        views: [
            [false, "activity"],
            [false, "kanban"],
            [false, "list"],
        ],
    },
]);

describe.current.tags("desktop");

async function setupForActivityView(views) {
    const documentIds = [2, 3, 4];
    const activityIds = documentIds;
    const todoTypeId = 1;
    const activities = documentIds.map((docId) => ({
        id: docId, // activityId = documentId for convenience
        activity_type_id: todoTypeId,
        can_write: true,
        res_id: docId,
        res_model: "documents.document",
    }));
    onRpc("get_activity_data", (kwargs) => {
        const grouped_activities = Object.fromEntries(
            documentIds.map((docId) => [
                docId,
                {
                    [todoTypeId]: {
                        count_by_state: { planned: 1 },
                        ids: [docId], // activityId == documentId see above
                        reporting_date: "2025-09-30",
                        state: "planned",
                        user_assigned_ids: [1],
                        summaries: ["To-Do"],
                    },
                },
            ])
        );
        return {
            activity_res_ids: activityIds,
            activity_types: [{ id: 1, name: "To-Do", template_ids: [] }],
            grouped_activities,
        };
    });

    DocumentsModels.DocumentsDocument._views = views;
    const documentBaseData = {
        ...embeddedActionsServerData,
        "documents.document": embeddedActionsServerData["documents.document"].map((d) => ({
            ...d,
            activity_ids: documentIds.includes(d.id) ? [d.id] : [],
        })),
    };
    const serverData = {
        "mail.activity.type": [{ id: todoTypeId, name: "todo" }],
        "mail.activity": activities,
        ...documentBaseData,
    };
    await makeDocumentsMockEnv({ serverData });
    await mountWithCleanup(WebClient);
}

test("Keep showing actions on view switch except for activity view", async function () {
    const views = {
        kanban: basicDocumentsKanbanArch,
        list: basicDocumentsListArch,
        activity: basicDocumentsActivityArch,
        [["search", false]]: getEnrichedSearchArch(),
    };

    await setupForActivityView(views);
    await getService("action").doAction(1);

    expect(`.o_kanban_view .o_content.o_component_with_search_panel`).toHaveCount(1);
    await contains(`.o_kanban_record:contains('Request 1')`).click();
    await waitFor(".o_control_panel_actions:contains('Action 1')");

    await getService("action").switchView("list");
    await waitFor(".o_data_row:contains('Request 1')");
    await waitFor(".o_control_panel_actions:contains('Action 1')");

    await getService("action").switchView("kanban");
    await waitFor(".o_kanban_record:contains('Request 1')");
    await waitFor(".o_control_panel_actions:contains('Action 1')");

    // We test more deeply the activity view as it is more customized in documents
    await getService("action").switchView("activity");
    expect(".o_selection_box").toHaveCount(0, {
        message: "Switching to activity view must clear the selection",
    });
    await contains(".o_activity_record:contains('Request 1')").click();
    await waitFor(".o_control_panel_actions:contains('Action 1')");
    expect(".o_selection_box").toHaveText("1\nselected");
    await contains(".o_activity_record:contains('Request 2')").click();
    await waitFor(".o_control_panel_actions:contains('Action 2 only')");
    expect(".o_selection_box").toHaveText("1\nselected");
    await contains(".o_selection_box .oi[data-icon='close_small']").click();
    await waitFor(".o_searchview_input_container");
    expect(".o_selection_box").toHaveCount(0);
    expect(".o_control_panel_actions:contains('Action 2 only')").toHaveCount(0);
    expect(".o_cp_action_menus .o_dropdown_title:contains('Actions')").toHaveCount(0);
    await contains(".o_activity_record:contains('Request 3')").click();
    await waitFor(".o_control_panel_actions:contains('Action 2 and 3')");
    expect(".o_selection_box").toHaveText("1\nselected");
    expect(".o_control_panel_actions button:contains('Share')").toHaveCount(1);
    await contains(".o_cp_action_menus .o_dropdown_title:contains('Actions')").click();
    await waitFor(".o-dropdown--menu .o-dropdown-item:contains('Create Shortcut')");

    await getService("action").switchView("kanban");
    await waitFor(".o_record_selected:contains('Request 3')");
});

test("Ensure search panel data are loaded on activity view load", async function () {
    const simplifiedDocumentsListArch = basicDocumentsListArch.replace(
        'js_class="documents_list"',
        ""
    );
    const views = {
        kanban: basicDocumentsKanbanArch,
        list: simplifiedDocumentsListArch,
        activity: basicDocumentsActivityArch,
        [["search", false]]: getEnrichedSearchArch(),
    };

    await setupForActivityView(views);
    await getService("action").doAction(2);

    await contains("span:contains('Schedule activity')").click();
    await contains("button.btn.o_form_button_cancel.btn-secondary").click();

    await contains("tr:nth-child(1) td.o_activity_summary_cell.p-0.h-100.planned div").click();
    await contains("div.o-mail-ActivityListPopover.d-flex.flex-column button").click();
    await contains("button.btn.btn-primary.o_form_button_save").click();

    await getService("action").switchView("kanban");
    expect(`.o_kanban_view .o_content.o_component_with_search_panel`).toHaveCount(1);

    await getService("action").switchView("list");
    await waitFor(".o_data_row:contains('Request 1')");
});

test("Check deep search across views", async function () {
    const serverData = getDocumentsTestServerModelsData([
        makeDocumentRecordData(2, "Folder 2", { type: "folder", folder_id: 1 }),
        makeDocumentRecordData(3, "Folder 3", { type: "folder", folder_id: 2 }),
        makeDocumentRecordData(4, "Folder 4", { type: "folder", folder_id: 3 }),
    ]);
    DocumentsModels.DocumentsDocument._views = {
        kanban: basicDocumentsKanbanArch,
        list: basicDocumentsListArch,
        [["search", false]]: getEnrichedSearchArch(),
    };
    await makeDocumentsMockEnv({ serverData });
    await mountWithCleanup(WebClient);
    await getService("action").doAction(1);

    //Open Folder 1 then open "Search in folder" from the search panel
    await contains(`.o_kanban_record:contains('Folder 1')`).click();
    await contains(
        ".o_search_panel_category_value[data-value-id='COMPANY'] .o_toggle_fold"
    ).click();
    await rightClick(".o_search_panel_label_title:contains('Folder 1')");
    await waitFor(".o-dropdown--menu");
    await contains(".o-dropdown--menu .o-dropdown-item:contains('Search in folder')").click();
    await waitFor(`.o_searchview .o_searchview_facet:contains('All children')`);
    expect(".o_searchview_input").toBeFocused();

    // Navigate inside Folder 2 (kanban card): deep search domain: child_of Folder 2 remain)
    await contains(`.o_kanban_record:contains('Folder 2')`).click();
    await waitForNone(`.o_kanban_record:contains('Folder 2')`);
    expect(`.o_searchview .o_searchview_facet:contains('All children')`).toHaveCount(1);

    // Switch to list view; search item is still there
    await getService("action").switchView("list");
    await waitFor(`.o_data_row td[name='name']:contains('Folder 3')`);
    expect(`.o_data_row td[name='name']:contains('Folder 4')`).toHaveCount(1);
    expect(`.o_searchview .o_searchview_facet:contains('All children')`).toHaveCount(1);

    // Navigate into Folder 3 (list row), then navigate back to Folder 2 via search panel;
    // since F3 is not an ancestor of F2, deep search is deactivated and Folder 4 disappears
    await contains(`.o_data_row:contains('Folder 3') .o_field_documents_type_icon`).click();
    expect(`.o_data_row td[name='name']:contains('Folder 3')`).toHaveCount(0);
    await contains(".o_search_panel_label_title:contains('Folder 2')").click();
    await waitForNone(`.o_data_row td[name='name']:contains('Folder 4')`);
    expect(`.o_data_row td[name='name']:contains('Folder 3')`).toHaveCount(1);

    expect(`.o_searchview .o_searchview_facet:contains('All children')`).toHaveCount(0);
});

test("Document Upload One File", async function () {
    onRpc("ir.model", "display_name_for", ({ args }) =>
        args[0].map((model) => ({ model, display_name: model }))
    );

    DocumentsModels.DocumentsDocument._views = {
        kanban: basicDocumentsKanbanArch,
        list: basicDocumentsListArch,
        [["search", false]]: getEnrichedSearchArch(),
    };

    localStorage.setItem("documentsChatterVisible", "true");

    const bus = new EventBus();
    let uploadResponse = "[102]";
    mockService("file_upload", {
        bus,
        upload: async (route) => {
            if (route === "/documents/upload/") {
                expect.step("upload_done");
                bus.trigger("FILE_UPLOAD_LOADED", {
                    upload: {
                        data: new FormData(),
                        xhr: { status: 200, response: uploadResponse },
                    },
                });
            }
        },
    });

    const serverData = getDocumentsTestServerModelsData([
        {
            folder_id: 1,
            id: 101,
            name: "File 1",
            access_token: "accessToken",
            type: "binary",
        },
        {
            folder_id: 1,
            id: 102,
            name: "File 2",
            access_token: "accessToken",
            type: "binary",
        },
    ]);

    await makeDocumentsMockEnv({ serverData });
    await mountWithCleanup(WebClient);
    await getService("action").doAction(1);

    await animationFrame();
    const file = new File(["hello world"], "text.txt", { type: "text/plain" });
    await inputFiles(".o_control_panel_main_buttons .o_input_file", [file]);
    await animationFrame();
    expect.verifySteps(["upload_done"]);
    await expect(".o_documents_details_panel").toBeVisible();
    await expect(".o_documents_details_panel_name input").toHaveValue("File 2");
    await expect(".o_selection_box b:contains('1')").toHaveCount(1); // 1 selected
    await expect(".o_record_selected").toHaveCount(1);
    await expect(".o_record_selected span:contains('File 2')").toHaveCount(1);
    await animationFrame();
    await expect(".o_control_panel_actions button:contains('Share')").toHaveCount(1); // action visible

    // switch to list view
    await getService("action").switchView("list");
    await waitFor(".o_data_row:contains('File 2')");
    await waitFor(".o_control_panel_actions:contains('Share')");
    await expect(".o_control_panel_actions button:contains('Share')").toHaveCount(1); // action still visible

    await getService("action").switchView("kanban");
    await waitFor(".o_kanban_record:contains('File 1')");
    await waitFor(".o_control_panel_actions:contains('Share')");
    await expect(".o_control_panel_actions button:contains('Share')").toHaveCount(1); // action still visible

    // now upload 2 files
    // the share action is not visible, we view the first documents in the detail panel
    // but both are selected
    uploadResponse = "[101, 102]";
    await inputFiles(".o_control_panel_main_buttons .o_input_file", [file, file]);
    await animationFrame();
    expect.verifySteps(["upload_done"]);
    await expect(".o_documents_details_panel_name input").toHaveValue("File 1");
    await expect(".o_selection_box b:contains('2')").toHaveCount(1); // 2 selected
    await expect(".o_record_selected").toHaveCount(2);
    await expect(".o_record_selected span:contains('File 1')").toHaveCount(1);
    await expect(".o_record_selected span:contains('File 2')").toHaveCount(1);
});
