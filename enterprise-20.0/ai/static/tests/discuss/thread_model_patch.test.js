import { insertText, setupChatHub, start, startServer } from "@mail/../tests/mail_test_helpers";

import { waitFor, waitForNone, describe, expect, test } from "@odoo/hoot";
import { press } from "@odoo/hoot-dom";

import { Command, contains, getService, onRpc, serverState } from "@web/../tests/web_test_helpers";
import { defineAIModels } from "../ai_test_helpers";

describe.current.tags("desktop");
defineAIModels();

test("posting in ai chat starts callback-driven response generation", async () => {
    const pyEnv = await startServer();
    const partnerId = pyEnv["res.partner"].create({ name: "Agent Partner" });
    const aiAgentId = pyEnv["ai.agent"].create({
        name: "Agent Partner",
        partner_id: partnerId,
        sources_ids: [Command.create({ name: "instructions.txt" })],
    });
    const channelId = pyEnv["discuss.channel"].create({
        channel_member_ids: [
            Command.create({ partner_id: serverState.partnerId }),
            Command.create({ partner_id: partnerId }),
        ],
        channel_type: "ai_chat",
        ai_agent_id: aiAgentId,
    });
    pyEnv["ai.session"].create({
        agent_id: aiAgentId,
        channel_id: channelId,
        loop_state: "ready",
    });
    onRpc("/ai/start_session_advance", () => {
        expect.step("start session advance");
        return {
            loop_state: "waiting_model",
        };
    });
    setupChatHub({ opened: [channelId] });
    await start();
    await waitFor(".o-mail-ChatWindow");
    await contains("button[title='More Actions']").click();

    // Test session options buttons
    await contains("button[name='toggle-web-search']").click();
    await waitFor("button[name='toggle-web-search'] input[type='checkbox']:checked");

    await contains("button[name='toggle-restrict-to-resources']").click();
    await waitFor("button[name='toggle-web-search'] input[type='checkbox']:not(:checked)");
    await waitFor("button[name='toggle-restrict-to-resources'] input[type='checkbox']:checked");

    await contains("button[name='toggle-think-longer']").click();
    await waitFor("button[name='toggle-think-longer'] input[type='checkbox']:checked");

    await contains("button[name='toggle-action-auto-approve']").click();
    await waitFor("button[name='toggle-action-auto-approve'] input[type='checkbox']:checked");

    await contains(".o-mail-ChatWindow .o-mail-Composer-input").click();
    await insertText(".o-mail-ChatWindow .o-mail-Composer-input", "AI is bad at writing code");
    await press("Enter");
    await expect.waitForSteps(["start session advance"]);
});

test("loop state controls sending while the agent or its subagent is busy", async () => {
    const pyEnv = await startServer();
    const partnerId = pyEnv["res.partner"].create({ name: "Agent Partner" });
    const aiAgentId = pyEnv["ai.agent"].create({
        name: "Agent Partner",
        partner_id: partnerId,
    });
    const channelId = pyEnv["discuss.channel"].create({
        channel_member_ids: [
            Command.create({ partner_id: serverState.partnerId }),
            Command.create({ partner_id: partnerId }),
        ],
        channel_type: "ai_chat",
        ai_agent_id: aiAgentId,
    });
    const sessionId = pyEnv["ai.session"].create({
        agent_id: aiAgentId,
        channel_id: channelId,
        loop_state: "ready",
    });
    onRpc("/ai/start_session_advance", () => {
        expect.step("start session advance");
        return {
            loop_state: "waiting_model",
        };
    });
    setupChatHub({ opened: [channelId] });
    await start();
    await waitFor(".o-mail-ChatWindow");
    await contains(".o-mail-ChatWindow .o-mail-Composer-input").click();
    await insertText(".o-mail-ChatWindow .o-mail-Composer-input", "First message");
    await press("Enter");
    await expect.waitForSteps(["start session advance"]);
    await insertText(".o-mail-ChatWindow .o-mail-Composer-input", "Second message");
    await waitFor(".o-mail-Composer button[name='send-message']:disabled");
    await waitFor(".o-ai-tool-status:contains(Thinking)");
    await waitForNone(".o-mail-ChatWindow-typing");
    const store = getService("mail.store");
    for (const loop_state of ["waiting_child", "waiting_client_result"]) {
        store["ai.session"].insert({ id: sessionId, loop_state });
        await waitFor(".o-mail-Composer button[name='send-message']:disabled");
        await waitFor(".o-ai-tool-status:contains(Thinking)");
    }
    for (const loop_state of ["waiting_confirmation", "waiting_answer", "ready"]) {
        store["ai.session"].insert({ id: sessionId, loop_state });
        await waitFor(".o-mail-Composer button[name='send-message']:enabled");
        await waitForNone(".o-ai-tool-status");
    }
    const child = store["ai.session"].insert({
        id: sessionId + 1,
        channel_id: channelId,
        parent_session_id: sessionId,
    });
    for (const loop_state of ["waiting_confirmation", "waiting_answer"]) {
        child.loop_state = loop_state;
        await waitFor(".o-mail-Composer button[name='send-message']:disabled");
    }
    child.loop_state = "ready";
    await waitFor(".o-mail-Composer button[name='send-message']:enabled");

    onRpc("/ai/resume_pending_interaction", async (request) => {
        const { params } = await request.json();
        expect(params.session_id).toBe(child.id);
        expect(params.resume_token).toBe("child-confirmation");
        expect(params.response).toEqual({ kind: "confirmation", value: "confirm_once" });
        expect.step("child confirmed");
        return { loop_state: "ready", interactionConsumed: true };
    });
    child.loop_state = "waiting_confirmation";
    child.userInputRequest = {
        type: "confirmation",
        body: "Create the contact?",
        choices: [{ label: "Yes, do it", value: "confirm_once" }],
        resumeToken: "child-confirmation",
    };
    const prompt = ".o_ai_user_input_request";
    await waitFor(prompt);
    expect(prompt + " .fw-bold").toHaveText("Agent Partner");
    await contains(prompt + " button:contains('Yes, do it')").click();
    await expect.waitForSteps(["child confirmed"]);
    await waitForNone(prompt);

    // Livechat retains the native typing indicator while callbacks are pending.
    store["discuss.channel"].get(channelId).channel_type = "livechat";
    child.loop_state = "waiting_model";
    await waitFor(".o-mail-ChatWindow-typing");
    child.loop_state = "ready";
    await waitForNone(".o-mail-ChatWindow-typing");
});
