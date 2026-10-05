import {
    click,
    contains,
    insertText,
    openDiscuss,
    openMessagingMenu,
    setupChatHub,
    startServer,
    start,
    MENU_ACTIVE_IDS,
} from "@mail/../tests/mail_test_helpers";
import { aiSessionIdentifier } from "@ai/utils/ai_session_identifier";
import { runOneWayClientToolBatch } from "@ai/discuss/core/common/ai_client_tool_service";
import { createAIChat, defineAIModels } from "./ai_test_helpers";
import { DiscussChannel } from "./mock_server/mock_models/discuss_channel";
import { expect, test } from "@odoo/hoot";
import { waitFor } from "@odoo/hoot-dom";
import {
    Command,
    defineActions,
    defineMenus,
    getService,
    makeKwArgs,
    onRpc,
    patchWithCleanup,
    serverState,
} from "@web/../tests/web_test_helpers";

const RESUME_PREVIOUS_CHAT_SELECTOR = ".o-mail-ChatWindow a:text('Resume previous chat')";

function mockSuggestedAiChannel(channelId) {
    patchWithCleanup(DiscussChannel.prototype, {
        _get_suggested_ai_channel() {
            return this.env["discuss.channel"].browse(channelId);
        },
    });
}

defineAIModels();
defineActions([
    {
        id: 667,
        tag: "action_1",
        xml_id: "action_1",
        name: "Partners Action 1",
        res_model: "partner",
        views: [[false, "kanban"]],
    },
    {
        id: 668,
        tag: "action_2",
        xml_id: "action_2",
        name: "Partners Action 2",
        res_model: "partner",
        views: [[false, "list"]],
    },
]);
defineMenus([
    {
        id: 1,
        name: "App1",
        appID: 1,
        actionID: 667,
    },
    {
        id: 2,
        name: "App2",
        appID: 2,
        actionID: 668,
    },
]);

test.tags("desktop");
test("AI chats are shown in their Discuss section", async () => {
    const pyEnv = await startServer();
    const channelId = pyEnv["ai.agent"].action_launch_ai_chat("systray_ai_button").ai_channel_id;
    await start();
    await openDiscuss(channelId);
    await contains(".o-mail-MessagingMenu-tab.active:has(:text('AI'))");
    await contains(".o-mail-MessagingMenuItem:has(:text('Test AI Agent'))");
});

test.tags("desktop");
test("expanding an AI chat opens only the AI chats tab", async () => {
    const pyEnv = await startServer();
    const agentPartnerId = pyEnv["res.partner"].create({ name: "Test AI Agent" });
    const agentId = pyEnv["ai.agent"].create({
        name: "Test AI Agent",
        partner_id: agentPartnerId,
    });
    const aiChannelId = pyEnv["discuss.channel"].create({
        ai_agent_id: agentId,
        channel_member_ids: [
            Command.create({ partner_id: serverState.partnerId }),
            Command.create({ partner_id: agentPartnerId }),
        ],
        channel_type: "ai_chat",
        name: "Test AI Agent",
    });
    pyEnv["discuss.channel"].create({ name: "General" });
    setupChatHub({ opened: [aiChannelId] });
    await start();
    await contains(".o-mail-ChatWindow:has(:text('Test AI Agent'))");
    await click(".o-mail-ChatWindow button[name='expand-discuss']");
    await contains(".o-mail-MessagingMenu-tab.active:has(:text('AI'))");
});

test.tags("desktop");
test("AI chat messaging menu preview shows the latest message", async () => {
    const pyEnv = await startServer();
    const agentPartnerId = pyEnv["res.partner"].create({ name: "Test AI Agent" });
    const agentId = pyEnv["ai.agent"].create({
        name: "Test AI Agent",
        partner_id: agentPartnerId,
    });
    const channelId = pyEnv["discuss.channel"].create({
        ai_agent_id: agentId,
        channel_member_ids: [
            Command.create({ partner_id: serverState.partnerId }),
            Command.create({ partner_id: agentPartnerId }),
        ],
        channel_type: "ai_chat",
        name: "Test AI Agent",
    });
    const needactionMessageId = pyEnv["mail.message"].create({
        author_id: agentPartnerId,
        body: "older AI answer",
        message_type: "comment",
        model: "discuss.channel",
        needaction: true,
        res_id: channelId,
    });
    pyEnv["mail.notification"].create({
        mail_message_id: needactionMessageId,
        notification_status: "sent",
        notification_type: "inbox",
        res_partner_id: serverState.partnerId,
    });
    pyEnv["mail.message"].create({
        author_id: serverState.partnerId,
        body: "newer user prompt",
        message_type: "comment",
        model: "discuss.channel",
        res_id: channelId,
    });

    await start();
    await openMessagingMenu(MENU_ACTIVE_IDS.AI_CHAT);
    await contains(".o-mail-NotificationItem", { count: 1 });
    expect(".o-mail-NotificationItem-text").toHaveText("You: newer user prompt");
});

test.tags("desktop");
test("AI tab in the messaging menu shows and reopens AI chats", async () => {
    const pyEnv = await startServer();
    const agentPartnerId = pyEnv["res.partner"].create({ name: "Test AI Agent" });
    const agentId = pyEnv["ai.agent"].create({
        name: "Test AI Agent",
        partner_id: agentPartnerId,
    });
    pyEnv["discuss.channel"].create({
        ai_agent_id: agentId,
        channel_member_ids: [
            Command.create({ partner_id: serverState.partnerId }),
            Command.create({ partner_id: agentPartnerId }),
        ],
        channel_type: "ai_chat",
        name: "Test AI Agent",
    });
    pyEnv["discuss.channel"].create({ name: "General" });

    await start();
    await openMessagingMenu(MENU_ACTIVE_IDS.AI_CHAT);
    await contains(".o-mail-NotificationItem", { count: 1 });
    await contains(".o-mail-NotificationItem-name:text('Test AI Agent')");
    await click(".o-mail-NotificationItem-name:text('Test AI Agent')");
    await contains(".o-mail-ChatWindow:has(:text('Test AI Agent'))");
});

test.tags("desktop");
test("a new AI chat suggests and reopens a matching non-empty chat that is not open", async () => {
    const pyEnv = await startServer();
    const previousChannelId =
        pyEnv["ai.agent"].action_launch_ai_chat("systray_ai_button").ai_channel_id;
    const [messageId] = pyEnv["discuss.channel"].message_post(
        previousChannelId,
        makeKwArgs({
            body: "Previous question",
            message_type: "comment",
        }),
    );
    pyEnv["discuss.channel"].write([previousChannelId], { message_ids: [messageId] });
    mockSuggestedAiChannel(previousChannelId);
    const restoredChannelId =
        pyEnv["ai.agent"].action_launch_ai_chat("systray_ai_button").ai_channel_id;
    setupChatHub({ opened: [restoredChannelId] });

    await start();

    await contains(RESUME_PREVIOUS_CHAT_SELECTOR);
    await click(RESUME_PREVIOUS_CHAT_SELECTOR);
    await contains(RESUME_PREVIOUS_CHAT_SELECTOR, { count: 0 });
    await contains(".o-mail-ChatWindow", { count: 1 });
    await contains(".o-mail-ChatWindow:has(:text('Previous question'))");
});

test.tags("desktop");
test("a new AI chat does not suggest a matching non-empty chat that is already open", async () => {
    const pyEnv = await startServer();
    const channelId = pyEnv["ai.agent"].action_launch_ai_chat("systray_ai_button").ai_channel_id;
    const [messageId] = pyEnv["discuss.channel"].message_post(
        channelId,
        makeKwArgs({
            body: "Previous question",
            message_type: "comment",
        }),
    );
    pyEnv["discuss.channel"].write([channelId], { message_ids: [messageId] });
    mockSuggestedAiChannel(channelId);
    setupChatHub({ opened: [channelId] });

    await start();
    await contains(".o-mail-ChatWindow:has(:text('Test AI Agent'))");
    await getService("aiChatLauncher").launchAIChat({
        interfaceKey: "systray_ai_button",
    });

    await contains(RESUME_PREVIOUS_CHAT_SELECTOR, { count: 0 });
});

test.tags("desktop");
test("a new AI chat suggests a matching non-empty chat that is minimized", async () => {
    const pyEnv = await startServer();
    const channelId = pyEnv["ai.agent"].action_launch_ai_chat("systray_ai_button").ai_channel_id;
    const [messageId] = pyEnv["discuss.channel"].message_post(
        channelId,
        makeKwArgs({
            body: "Previous question",
            message_type: "comment",
        }),
    );
    pyEnv["discuss.channel"].write([channelId], { message_ids: [messageId] });
    mockSuggestedAiChannel(channelId);
    setupChatHub({ folded: [channelId] });

    await start();
    await getService("aiChatLauncher").launchAIChat({
        interfaceKey: "systray_ai_button",
    });

    await contains(RESUME_PREVIOUS_CHAT_SELECTOR);
});

test.tags("mobile");
test("AI tab is available in the mobile Discuss navbar", async () => {
    const pyEnv = await startServer();
    const agentPartnerId = pyEnv["res.partner"].create({ name: "Test AI Agent" });
    const agentId = pyEnv["ai.agent"].create({
        name: "Test AI Agent",
        partner_id: agentPartnerId,
    });
    pyEnv["discuss.channel"].create({
        ai_agent_id: agentId,
        channel_member_ids: [
            Command.create({ partner_id: serverState.partnerId }),
            Command.create({ partner_id: agentPartnerId }),
        ],
        channel_type: "ai_chat",
        name: "Test AI Agent",
    });
    pyEnv["discuss.channel"].create({ name: "General" });

    await start();
    await openDiscuss();
    await contains(".o-mail-MessagingMenu-tab:text('AI')");
    await click(".o-mail-MessagingMenu-tab:text('AI')");
    await contains(".o-mail-MessagingMenu-tab.active:text('AI')");
    await contains(".o-mail-NotificationItem", { count: 1 });
    await contains(".o-mail-NotificationItem-name:text('Test AI Agent')");
});

test.tags("desktop");
test("Closing an empty AI chat deletes the channel", async () => {
    const pyEnv = await startServer();
    const channelId = pyEnv["ai.agent"].action_launch_ai_chat("systray_ai_button").ai_channel_id;
    onRpc("discuss.channel", "unlink", ({ args }) => {
        expect.step("unlink");
        expect(args).toEqual([channelId]);
    });
    setupChatHub({ opened: [channelId] });

    await start();
    await contains(".o-mail-ChatWindow");
    await getService("mail.store")["mail.thread"].get({
        model: "discuss.channel",
        id: channelId,
    }).isLoadedPromise;
    await click(".o-mail-ChatWindow-header [title*='Close Chat Window']");
    await contains(".o-mail-ChatWindow", { count: 0 });
    await expect.waitForSteps(["unlink"]);
});

test.tags("desktop");
test("Closing an AI chat with messages does not delete the channel", async () => {
    onRpc("discuss.channel", "unlink", () => {
        expect.step("unlink");
    });
    const pyEnv = await startServer();
    const channelId = pyEnv["ai.agent"].action_launch_ai_chat("systray_ai_button").ai_channel_id;
    pyEnv["mail.message"].create({
        author_id: serverState.partnerId,
        body: "Hello",
        message_type: "comment",
        model: "discuss.channel",
        res_id: channelId,
    });
    setupChatHub({ opened: [channelId] });

    await start();
    await contains(".o-mail-ChatWindow .o-mail-Message");
    await click(".o-mail-ChatWindow-header [title*='Close Chat Window']");
    await contains(".o-mail-ChatWindow", { count: 0 });
    expect.verifySteps([]);
});

test.tags("desktop");
test("Deleting a non-empty AI chat from Discuss asks for confirmation", async () => {
    const pyEnv = await startServer();
    const channelId = pyEnv["ai.agent"].action_launch_ai_chat("systray_ai_button").ai_channel_id;
    pyEnv["mail.message"].create({
        author_id: serverState.partnerId,
        body: "Hello",
        message_type: "comment",
        model: "discuss.channel",
        res_id: channelId,
    });
    onRpc("discuss.channel", "unlink", ({ args }) => {
        expect.step("unlink");
        expect(args).toEqual([channelId]);
    });

    await start();
    await openDiscuss(channelId);
    await contains(".o-mail-DiscussContent .o-mail-Message");
    await click("[title='Chat Actions']");
    await click(".o-dropdown-item:text('Delete AI chat')");
    await contains(".modal");
    await click(".modal .btn-primary");
    await expect.waitForSteps(["unlink"]);
});

test.tags("desktop");
test("Deleting an empty AI chat from Discuss does not ask for confirmation", async () => {
    const pyEnv = await startServer();
    const channelId = pyEnv["ai.agent"].action_launch_ai_chat("systray_ai_button").ai_channel_id;
    onRpc("discuss.channel", "unlink", ({ args }) => {
        expect.step("unlink");
        expect(args).toEqual([channelId]);
    });

    await start();
    await openDiscuss(channelId);
    await click("[title='Chat Actions']");
    await click(".o-dropdown-item:text('Delete AI chat')");
    await expect.waitForSteps(["unlink"]);
});

test.tags("desktop");
test("Command i.e. /help shouldn't call the LLM", async () => {
    onRpc("/ai/start_session_advance", () => {
        throw new Error("Shouldn't be called");
    });
    const pyEnv = await startServer();
    const agentPartnerId = pyEnv["ai.agent"].create({ name: "Test Agent" });
    const agentId = pyEnv["ai.agent"].create({ name: "Test Agent", partner_id: agentPartnerId });
    const channelId = pyEnv["discuss.channel"].create({
        name: "General",
        channel_type: "ai_chat",
        ai_agent_id: agentId,
    });
    await start();
    await openDiscuss(channelId);
    await insertText(".o-mail-Composer-input", "/help");
    await click(".o-mail-Composer button[name='send-message']:enabled");
    await contains(".o-mail-Message", { count: 1 });
    await contains(".o-mail-Message:eq(0):has(:text('OdooBot'))");
});

test.tags("desktop");
test("Opening a view with an agent updates the menu and formats the help message", async () => {
    const pyEnv = await startServer();
    const partnerId = pyEnv["res.partner"].create({ name: "Test Agent" });
    const agentId = pyEnv["ai.agent"].create({ name: "Test Agent", partner_id: partnerId });
    const { channelId } = createAIChat(pyEnv, agentId);
    onRpc("/ai/start_session_advance", () => ({ loop_state: "waiting_model" }));

    await start();
    // Let the default app finish loading before opening another action.
    await waitFor(".o_menu_brand");
    expect(".o_menu_brand").toHaveText("App1");
    await openDiscuss(channelId);

    await insertText(".o-mail-Composer-input", "hello");
    await click(".o-mail-Composer button[name='send-message']:enabled");
    await runOneWayClientToolBatch(getService("mail.store"), {
        channel_id: channelId,
        aiSessionIdentifier,
        commands: [
            {
                name: "show_view",
                oneway: true,
                params: {
                    action: {
                        id: 668,
                        type: "ir.actions.act_window",
                        tag: "action_2",
                        xml_id: "action_2",
                        name: "Partners Action 2",
                        res_model: "partner",
                        domain: [["id", "=", 0]],
                        views: [[false, "list"]],
                        help: `<p class="o_view_nocontent_smiling_face">No records</p>`,
                    },
                    menuId: 2,
                },
            },
        ],
    });

    await waitFor(".o_list_view");
    await waitFor(".o_view_nocontent_smiling_face");
    expect(".o_view_nocontent_smiling_face").toHaveText("No records");
    await waitFor(".o_menu_brand");
    expect(".o_menu_brand").toHaveText("App2");
});
