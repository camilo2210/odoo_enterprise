import { aiModels, createAIChat } from "@ai/../tests/ai_test_helpers";
import { hrModels } from "@hr/../tests/hr_test_helpers";
import { expectElementCount } from "@html_editor/../tests/_helpers/ui_expectations";
import {
    click,
    contains,
    insertText,
    openDiscuss,
    start,
    startServer,
} from "@mail/../tests/mail_test_helpers";
import { animationFrame, describe, test } from "@odoo/hoot";
import { defineModels } from "@web/../tests/web_test_helpers";

describe.current.tags("desktop");
defineModels({
    ...hrModels, // FIXME: somehow test non-deterministically needs "hr.employee", cf. https://runbot.odoo.com/runbot/build/92414152
    ...aiModels,
});

test("can handle command and disable mentions in AI composer", async () => {
    const pyEnv = await startServer();
    const agentPartnerId = pyEnv["res.partner"].create({ name: "Agent Partner" });
    const aiAgentId = pyEnv["ai.agent"].create({
        name: "Test Agent",
        partner_id: agentPartnerId,
    });
    const { channelId } = createAIChat(pyEnv, aiAgentId);
    await start();
    await openDiscuss(channelId);
    await insertText(".o-mail-Composer-input", "/help");
    await click(".o-mail-Composer button[title='Send (Enter)']:enabled");
    await contains(".o-mail-Message");
    await insertText(".o-mail-Composer-input", "@");
    await animationFrame();
    await expectElementCount(".o-mail-NavigableList-item", 0);
});
