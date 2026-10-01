import { test } from "@odoo/hoot";
import { makeMockServer, getService } from "@web/../tests/web_test_helpers";
import {
    triggerHotkey,
    start,
    insertText,
    contains,
    click,
} from "@mail/../tests/mail_test_helpers";
import { defineAIModels } from "@ai/../tests/ai_test_helpers";

defineAIModels();

test.tags("desktop");
test("[text composer] can open chat with @agent in command palette with focused composer", async () => {
    const mockServer = await makeMockServer();

    const partnerId = mockServer.env["res.partner"].create({
        name: "Test agent",
        active: false,
    });
    mockServer.env["ai.agent"].create({
        name: "Test agent",
        partner_id: partnerId,
    });

    await start();
    triggerHotkey("control+k");
    await insertText(".o_command_palette_search input", "@");
    await contains(".o_command_category>.text-uppercase", { text: "Agents" });
    await insertText(".o_command_palette_search input[placeholder='Search conversations']", "Test agent");
    await click(".o_command:has([data-icon='settings'])", { text: "Test agent" });
    await contains("input.o-mail-DiscussContent-threadName:value(Test agent)");
    await contains(".o-mail-Composer.o-focused");
});

test.tags("desktop", "html composer");
test("can open chat with @agent in command palette with focused composer", async () => {
    const mockServer = await makeMockServer();
    const partnerId = mockServer.env["res.partner"].create({
        name: "AI Agent",
    });
    mockServer.env["ai.agent"].create({
        name: "Test Agent",
        partner_id: partnerId,
    });
    await start();
    const composerService = getService("mail.composer");
    composerService.setHtmlComposer();
    triggerHotkey("control+k");
    await insertText(".o_command_palette_search input", "@");
    await insertText(".o_command_palette_search input[placeholder='Search conversations']", "AI Agent");
    await click(".o_command:has([data-icon='settings'])", { text: "AI Agent" });
    await contains("input.o-mail-DiscussContent-threadName:value(AI Agent)");
    await contains(".o-mail-Composer.o-focused");
});
