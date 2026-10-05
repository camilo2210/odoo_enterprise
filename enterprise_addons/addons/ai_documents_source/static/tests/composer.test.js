import {
    contains,
    click,
    setupChatHub,
    start,
    startServer,
} from "@mail/../tests/mail_test_helpers";
import { describe, test } from "@odoo/hoot";
import {
    defineModels,
} from "@web/../tests/web_test_helpers";
import { DocumentsModels } from "@documents/../tests/helpers/data";
import { basicDocumentsKanbanArch } from "@documents/../tests/helpers/views/kanban";
import { getEnrichedSearchArch } from "@documents/../tests/helpers/views/search";

describe.current.tags("desktop");

DocumentsModels.DocumentsDocument._views = {
    kanban: basicDocumentsKanbanArch,
    [["search", false]]: getEnrichedSearchArch(),
};

defineModels(DocumentsModels);

test("Can 'Add from Documents' in chat window", async () => {
    // This might conflict with focusing next chat window
    const pyEnv = await startServer();
    const channelId = pyEnv["discuss.channel"].create({ name: "General" });
    setupChatHub({ opened: [channelId] });
    await start();
    await click(".o-mail-ChatWindow button[title='More Actions']");
    await click(".dropdown-item:has(:text('Add from Documents'))");
    await contains(".modal-title:text('Search: Documents')");
});
