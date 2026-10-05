import { describe, expect, test, waitFor } from "@odoo/hoot";
import { queryOne } from "@odoo/hoot-dom";
import {
    contains,
    defineActions,
    defineModels,
    getService,
    mountWithCleanup,
    onRpc,
} from "@web/../tests/web_test_helpers";
import { browser } from "@web/core/browser/browser";
import { WebClient } from "@web/webclient/webclient";
import {
    DocumentsModels,
    getDocumentsTestServerModelsData,
    makeDocumentRecordData,
} from "@documents/../tests/helpers/data";
import { makeDocumentsMockEnv } from "@documents/../tests/helpers/model";
import { basicDocumentsKanbanArch } from "@documents/../tests/helpers/views/kanban";
import { getEnrichedSearchArch } from "@documents/../tests/helpers/views/search";
import { mockKnowledgeCommentsService } from "@knowledge/../tests/knowledge_test_helpers";
import { KnowledgeArticleEmbedding } from "./helpers/data";

defineModels({ ...DocumentsModels, KnowledgeArticleEmbedding });
defineActions([
    {
        id: 1,
        name: "Documents",
        res_model: "documents.document",
        type: "ir.actions.act_window",
        views: [[false, "kanban"]],
    },
    {
        id: 2,
        xml_id: "knowledge.ir_actions_server_knowledge_home_page",
        name: "Article",
        res_model: "knowledge.article",
        res_id: 1,
        type: "ir.actions.act_window",
        views: [[false, "form"]],
    },
]);

describe.current.tags("desktop");

test("Embedded view of a folder is loaded with the token", async function () {
    onRpc("/documents/touch/<access_token>", () => ({}));
    onRpc("documents.document", "search_panel_select_range", async ({ parent, kwargs }) => {
        const { documents_shared_access_token: token, documents_unique_folder_id: user_folder_id } =
            kwargs.context;
        let step = "search_panel_select_range";
        if (user_folder_id) {
            step += ` for ${user_folder_id}`;
        }
        if (token) {
            step += ` with ${token}`;
        }
        expect.step(step);
        return parent();
    });

    DocumentsModels.DocumentsDocument._views = {
        kanban: basicDocumentsKanbanArch,
        [["search", false]]: getEnrichedSearchArch(),
    };
    const serverData = getDocumentsTestServerModelsData([
        makeDocumentRecordData(2, "File 1", { folder_id: 1 }),
    ]);
    await makeDocumentsMockEnv({ serverData });
    mockKnowledgeCommentsService();

    await mountWithCleanup(WebClient);
    // Embed folder view in article
    await getService("action").doAction(1);
    await contains(
        "li.o_search_panel_category_value:contains('COMPANY') button.o_toggle_fold"
    ).click();
    await contains("span.o_search_panel_label_title:contains('Folder 1')").click();
    expect.verifySteps(["search_panel_select_range"]);
    await contains("div.o_cp_action_menus .dropdown-toggle").click();
    await contains(".dropdown-menu .dropdown-toggle:contains(Knowledge)").click();
    await contains(".dropdown-menu .dropdown-item:contains('Insert view in article')").click();
    await contains(".modal-dialog td.o_field_cell:contains('Article 1')").click();
    await waitFor(".o_knowledge_editor .o_kanban_record:contains('File 1')");
    // The embedded view is loaded for the user having access to the folder
    expect.verifySteps(["search_panel_select_range for 1 with accessTokenFolder1"]);

    // The state stored in the article does not contain values.
    const embeddedProps = JSON.parse(
        queryOne('.o_knowledge_editor [data-embedded="view"]').dataset.embeddedProps
    );
    const state = JSON.parse(embeddedProps.viewProps.context.knowledge_search_model_state);
    const [, foldersSection] = state.sections[0];
    expect(foldersSection.values.map(([valueId]) => valueId)).toEqual([false]);

    // Ensure sure we always wait for the search panel to be loaded before fetching records.
    onRpc("documents.document", "web_search_read", async () => {
        expect.step("web_search_read");
    });

    browser.localStorage.removeItem("searchpanel_documents_document");
    await getService("action").doAction(2, {
        clearBreadcrumbs: true,
        props: { resId: 1 },
        viewType: "form",
    });
    await waitFor(".o_knowledge_editor .o_kanban_record:contains('File 1')");
    expect.verifySteps([
        `search_panel_select_range for 1 with accessTokenFolder1`,
        "web_search_read",
    ]);
});
