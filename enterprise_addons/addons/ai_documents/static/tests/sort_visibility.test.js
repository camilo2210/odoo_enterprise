import { user } from "@web/core/user";
import { describe, expect, test } from "@odoo/hoot";
import { animationFrame, waitFor } from "@odoo/hoot-dom";
import {
    contains,
    defineModels,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";
import {
    DocumentsModels,
    getDocumentsTestServerModelsData,
} from "@documents/../tests/helpers/data";
import { makeDocumentsMockEnv } from "@documents/../tests/helpers/model";
import { mountDocumentsKanbanView } from "@documents/../tests/helpers/views/kanban";

describe.current.tags("desktop");

defineModels(DocumentsModels);

test("Admin user should be able to see the Auto-sort item under the cog menu", async function () {
    const serverData = getDocumentsTestServerModelsData();
    const { name: folder1Name } = serverData["documents.document"][0];
    await makeDocumentsMockEnv({ serverData });
    patchWithCleanup(user, {
        hasGroup: () => true,
    });
    await mountDocumentsKanbanView();
    await waitFor(".o_kanban_renderer");

    await contains(`.o_kanban_record:contains(${folder1Name})`).click();
    await waitFor(`.o_last_breadcrumb_item:contains('${folder1Name}')`);
    await contains(".o_cp_action_menus [data-icon='more_vert']").click();
    await waitFor(`.o-dropdown-item`);
    expect(".o-dropdown-item:contains('Auto-sort')").toHaveCount(1);
});

test("Basic user shouldn't be able to see the Auto-sort item under the cog menu", async function () {
    const serverData = getDocumentsTestServerModelsData();
    const { name: folder1Name } = serverData["documents.document"][0];
    patchWithCleanup(user, {
        hasGroup: (group) => group === "base.group_user",
    });
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsKanbanView();
    await waitFor(".o_kanban_renderer");

    await contains(`.o_kanban_record:contains(${folder1Name})`).click();
    await waitFor(`.o_last_breadcrumb_item:contains('${folder1Name}')`);
    await animationFrame();
    expect(".o_cp_action_menus [data-icon='more_vert']").toHaveCount(0);
    expect(".o-dropdown-item:contains('Auto-sort')").toHaveCount(0);
});
