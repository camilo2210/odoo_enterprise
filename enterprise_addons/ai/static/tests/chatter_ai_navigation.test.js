import { runOneWayClientToolBatch } from "@ai/discuss/core/common/ai_client_tool_service";
import { aiSessionIdentifier } from "@ai/utils/ai_session_identifier";
import {
    click,
    contains,
    insertText,
    openFormView,
    start,
    startServer,
} from "@mail/../tests/mail_test_helpers";
import { test } from "@odoo/hoot";
import { Command, getService, onRpc, serverState } from "@web/../tests/web_test_helpers";
import { defineAIModels } from "./ai_test_helpers";

defineAIModels();

test.tags("desktop");
test("closing the full composer after the AI agent navigated away should not crash", async () => {
    const pyEnv = await startServer();
    const partnerId = pyEnv["res.partner"].create({ name: "Abigail Peterson" });
    const agentPartnerId = pyEnv["res.partner"].create({ name: "Agent Partner" });
    const aiAgentId = pyEnv["ai.agent"].create({
        name: "Agent Partner",
        partner_id: agentPartnerId,
    });
    const channelId = pyEnv["discuss.channel"].create({
        channel_member_ids: [
            Command.create({ partner_id: serverState.partnerId }),
            Command.create({ partner_id: agentPartnerId }),
        ],
        channel_type: "ai_chat",
        ai_agent_id: aiAgentId,
    });
    pyEnv["ai.session"].create({ agent_id: aiAgentId, channel_id: channelId });
    onRpc("/ai/start_session_advance", () => ({ loop_state: "waiting_model" }));
    await start();
    await openFormView("res.partner", partnerId);
    await contains(".o-mail-Chatter");
    await click("button", { text: "Send message" });
    await insertText(".o-mail-Composer-input", "hey");
    await click("button[title='Open Full Composer']");
    await contains(".o_dialog .o_form_view");

    // Simulate the AI agent navigating to another view while the full
    // composer dialog is still open: this tears down the current form view,
    // and with it the chatter of the partner, underneath the still-open
    // dialog.
    const channel = await getService("mail.store")["discuss.channel"].getOrFetch(channelId);
    await channel.post("show me all my contacts in the US");
    await runOneWayClientToolBatch(getService("mail.store"), {
        channel_id: channelId,
        aiSessionIdentifier,
        commands: [
            {
                name: "show_view",
                params: {
                    action: {
                        type: "ir.actions.act_window",
                        name: "Contacts",
                        res_model: "res.partner",
                        views: [[false, "list"]],
                    },
                    options: { clearBreadcrumbs: true },
                },
                oneway: true,
            },
        ],
    });
    await contains(".o_list_view");
    await contains(".o-mail-Chatter", { count: 0 });
    // make sure composer dialog is closed
    await contains(".o_dialog", { count: 0 });
});
