import { click, contains, openDiscuss, start, startServer } from "@mail/../tests/mail_test_helpers";
import { test } from "@odoo/hoot";
import { getService } from "@web/../tests/web_test_helpers";
import { defineAIModels } from "@ai/../tests/ai_test_helpers";

defineAIModels();

test.tags("desktop");
test("Can open a new AI chat from the scoped agent AI tab", async () => {
    const pyEnv = await startServer();
    const agentPartnerId = pyEnv["res.partner"].create({ name: "Scoped Agent" });
    const agentId = pyEnv["ai.agent"].create({
        name: "Scoped Agent",
        partner_id: agentPartnerId,
    });
    await start();
    await openDiscuss();
    const store = getService("mail.store");
    store.discuss.setScopedAiAgent(agentId);
    await contains(".o-mail-MessagingMenuEmpty", { text: "No AI Chats yet." });
    await click("button:has([data-icon='add']):text('Chat')");
    await contains(".o-mail-DiscussContent-threadName:value(Scoped Agent)");
});
