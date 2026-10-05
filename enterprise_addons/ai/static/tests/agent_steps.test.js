import { createAIChat, defineAIModels } from "@ai/../tests/ai_test_helpers";
import {
    click,
    contains,
    insertText,
    openDiscuss,
    start,
    startServer,
} from "@mail/../tests/mail_test_helpers";
import { Store } from "@mail/../tests/mock_server/store";
import { makeKwArgs, onRpc, serverState } from "@web/../tests/web_test_helpers";

import { describe, expect, test } from "@odoo/hoot";
import { press, queryAll, queryOne } from "@odoo/hoot-dom";

const THREAD_SELECTOR = ".o-mail-DiscussContent .o-mail-Thread";
const AGENT_HEADER_SELECTOR = ".o-agent-header";
const STEPS_BUTTON_SELECTOR = "button:text('Steps taken')";
const STEP_MSG_SELECTOR = ".o-mail-Message .o-ai-agent-step";
const TOOL_SUMMARY_SELECTOR = ".o-ai-agent-step .o-ai-tool-summary";
const RESPONSE_SELECTOR = ".o-mail-Message.o-ai-agent-response";
const PREVIEW_SELECTOR = ".o-mail-NotificationMessage";
const TOOL_STATUS_SELECTOR = ".o-ai-tool-status";

describe.current.tags("desktop");
defineAIModels();

async function openAgentStepsThread() {
    const pyEnv = await startServer();
    const agentPartnerId = pyEnv["res.partner"].create({ name: "Agent Partner" });
    const agentId = pyEnv["ai.agent"].create({
        name: "Agent Partner",
        partner_id: agentPartnerId,
    });
    const { channelId, sessionId } = createAIChat(pyEnv, agentId);
    const childPartnerId = pyEnv["res.partner"].create({ name: "Child Agent" });
    const childAgentId = pyEnv["ai.agent"].create({ name: "Child Agent", partner_id: childPartnerId });
    pyEnv["ai.session"].create({
        agent_id: childAgentId,
        parent_session_id: sessionId,
        channel_id: channelId,
    });
    const noteSubtypeId = pyEnv["mail.message.subtype"].search([
        ["subtype_xmlid", "=", "mail.mt_note"],
    ])[0];
    const commentSubtypeId = pyEnv["mail.message.subtype"].search([
        ["subtype_xmlid", "=", "mail.mt_comment"],
    ])[0];
    pyEnv["mail.message"].create([
        {
            author_id: serverState.partnerId,
            body: "Find matching leads",
            message_type: "comment",
            model: "discuss.channel",
            res_id: channelId,
            subtype_id: commentSubtypeId,
        },
        {
            author_id: childPartnerId,
            body: '<div class="o-ai-agent-step">Looking for matching leads</div>',
            message_type: "comment",
            model: "discuss.channel",
            res_id: channelId,
            subtype_id: noteSubtypeId,
        },
        {
            author_id: childPartnerId,
            body: '<div class="o-ai-agent-step"><div class="o-ai-tool-summary">Searched your leads</div></div>',
            message_type: "notification",
            model: "discuss.channel",
            res_id: channelId,
            subtype_id: noteSubtypeId,
        },
        {
            author_id: childPartnerId,
            body: "Here are the matching leads",
            message_type: "comment",
            model: "discuss.channel",
            res_id: channelId,
            subtype_id: commentSubtypeId,
        },
        {
            author_id: childPartnerId,
            body: "Leads Preview",
            message_type: "notification",
            model: "discuss.channel",
            res_id: channelId,
            subtype_id: commentSubtypeId,
        },
        {
            author_id: serverState.partnerId,
            body: "Prepare a follow-up",
            message_type: "comment",
            model: "discuss.channel",
            res_id: channelId,
            subtype_id: commentSubtypeId,
        },
        {
            author_id: agentPartnerId,
            body: '<div class="o-ai-agent-step">Preparing the follow-up</div>',
            message_type: "comment",
            model: "discuss.channel",
            res_id: channelId,
            subtype_id: noteSubtypeId,
        },
        {
            author_id: agentPartnerId,
            body: '<div class="o-ai-agent-step"><div class="o-ai-tool-summary">Created a follow-up</div></div>',
            message_type: "notification",
            model: "discuss.channel",
            res_id: channelId,
            subtype_id: noteSubtypeId,
        },
        {
            author_id: agentPartnerId,
            body: "The follow-up is ready",
            message_type: "comment",
            model: "discuss.channel",
            res_id: channelId,
            subtype_id: commentSubtypeId,
        },
    ]);

    await start();
    await openDiscuss(channelId);
}

test("agent step groups are folded by default", async () => {
    await openAgentStepsThread();
    // only the 2 final responses and the preview is shown
    await contains(PREVIEW_SELECTOR, { count: 1 });
    await contains(RESPONSE_SELECTOR, { count: 2 });
    await contains(STEP_MSG_SELECTOR, { count: 0 });
    await contains(TOOL_SUMMARY_SELECTOR, { count: 0 });
    await contains(TOOL_STATUS_SELECTOR, { count: 0 });
    // 2 final responses -> 2 times the agent header and the next steps button
    await contains(AGENT_HEADER_SELECTOR, { count: 2 });
    await contains(AGENT_HEADER_SELECTOR + ":eq(0)", { text: "Child Agent" });
    await contains(AGENT_HEADER_SELECTOR + ":eq(1)", { text: "Agent Partner" });
    await contains(STEPS_BUTTON_SELECTOR, { count: 2 });
    const responses = queryAll(RESPONSE_SELECTOR);
    for (const response of responses) {
        expect(response.previousElementSibling).toHaveClass("o-agent-header");
    }
    await contains(`${STEPS_BUTTON_SELECTOR} i[data-icon='chevron_right']`, { count: 2 });
});

test("Steps taken toggles its own group without affecting another group", async () => {
    await openAgentStepsThread();

    // open the first group of messages, containing one step msg and one tool summary
    await click(`${STEPS_BUTTON_SELECTOR}:eq(0)`);
    await contains(STEP_MSG_SELECTOR, { count: 1 });
    await contains(TOOL_SUMMARY_SELECTOR, { count: 1 });
    expect(queryOne(STEP_MSG_SELECTOR)).toHaveText("Looking for matching leads");
    expect(queryOne(TOOL_SUMMARY_SELECTOR)).toHaveText("Searched your leads");
    // both final responses and the preview should be shown
    await contains(RESPONSE_SELECTOR, { count: 2 });
    await contains(PREVIEW_SELECTOR, { count: 1 });
    // only the first step groups button changed
    await contains(`${STEPS_BUTTON_SELECTOR}:eq(0) i[data-icon='expand_more']`);
    await contains(`${STEPS_BUTTON_SELECTOR}:eq(1) i[data-icon='chevron_right']`);
    // header is shown above the step message
    expect(
        queryOne(STEP_MSG_SELECTOR).closest(".o-mail-Message").previousElementSibling,
    ).toHaveClass("o-agent-header");

    // clicking again should hide them
    await click(`${STEPS_BUTTON_SELECTOR}:eq(0)`);
    await contains(STEP_MSG_SELECTOR, { count: 0 });
    await contains(TOOL_SUMMARY_SELECTOR, { count: 0 });
    // final responses and preview should still be shown
    await contains(RESPONSE_SELECTOR, { count: 2 });
    await contains(PREVIEW_SELECTOR, { count: 1 });
    // agent headers as well
    await contains(AGENT_HEADER_SELECTOR, { count: 2 });
    await contains(STEPS_BUTTON_SELECTOR, { count: 2 });

    // open the second group of messages, containing one step msg and one tool summary
    await click(`${STEPS_BUTTON_SELECTOR}:eq(1)`);
    await contains(STEP_MSG_SELECTOR, { count: 1 });
    await contains(TOOL_SUMMARY_SELECTOR, { count: 1 });
    expect(queryOne(STEP_MSG_SELECTOR)).toHaveText("Preparing the follow-up");
    expect(queryOne(TOOL_SUMMARY_SELECTOR)).toHaveText("Created a follow-up");
    // both final responses and the preview should be shown
    await contains(RESPONSE_SELECTOR, { count: 2 });
    await contains(PREVIEW_SELECTOR, { count: 1 });
    // agent headers as well
    await contains(AGENT_HEADER_SELECTOR, { count: 2 });
    await contains(STEPS_BUTTON_SELECTOR, { count: 2 });
});

test("incoming agent step are hidden until clicking on the tool status", async () => {
    const pyEnv = await startServer();
    const agentPartnerId = pyEnv["res.partner"].create({ name: "Agent Partner" });
    const agentId = pyEnv["ai.agent"].create({
        name: "Agent Partner",
        partner_id: agentPartnerId,
    });
    const { channelId, sessionId } = createAIChat(pyEnv, agentId);
    pyEnv["mail.message"].create({
        author_id: serverState.partnerId,
        body: "Previous user message",
        message_type: "comment",
        model: "discuss.channel",
        res_id: channelId,
    });
    onRpc("/ai/start_session_advance", () => {
        const channel = pyEnv["discuss.channel"].browse(channelId)[0];
        pyEnv["discuss.channel"].message_post(
            channelId,
            makeKwArgs({
                author_id: agentPartnerId,
                body: '<div class="o-ai-agent-step">Searching the latest matching leads</div>',
                message_type: "comment",
                subtype_xmlid: "mail.mt_note",
            }),
        );
        pyEnv["bus.bus"]._sendone(
            channel,
            "mail.record/insert",
            new Store()
                .add(pyEnv["ai.session"].browse(sessionId), {
                    toolStatus: "Searching matching leads",
                    loop_state: "waiting_model",
                })
                .as_dict(),
        );
        expect.step("agent_step");
        return { loop_state: "waiting_model" };
    });

    await start();
    await openDiscuss(channelId);
    // a thread ending with a user message has no agent group or tool status
    await contains(`${THREAD_SELECTOR} .o-mail-Message:has(:text('Previous user message'))`);
    await contains(STEP_MSG_SELECTOR, { count: 0 });
    await contains(AGENT_HEADER_SELECTOR, { count: 0 });
    await contains(STEPS_BUTTON_SELECTOR, { count: 0 });
    await contains(TOOL_STATUS_SELECTOR, { count: 0 });

    await insertText(".o-mail-Composer-input", "Find matching leads");
    await press("Enter");
    await expect.waitForSteps(["agent_step"]);

    // with Show Steps disabled, only the folded toolStatus should be shown
    await contains(STEP_MSG_SELECTOR, { count: 0 });
    await contains(AGENT_HEADER_SELECTOR, { count: 0 });
    await contains(STEPS_BUTTON_SELECTOR, { count: 0 });
    await contains(RESPONSE_SELECTOR, { count: 0 });
    await contains(PREVIEW_SELECTOR, { count: 0 });
    await contains(TOOL_STATUS_SELECTOR, { count: 1 });
    await contains(`${TOOL_STATUS_SELECTOR}:is(button)`);
    expect(queryOne(`${TOOL_STATUS_SELECTOR}:is(button)`)).toHaveText("Searching matching leads");

    // clicking on the tool status reveals the agent header and the step message
    await click(TOOL_STATUS_SELECTOR);
    await contains(STEP_MSG_SELECTOR);
    expect(queryOne(STEP_MSG_SELECTOR)).toHaveText("Searching the latest matching leads");
    await contains(AGENT_HEADER_SELECTOR);
    await contains(STEPS_BUTTON_SELECTOR);
    // steps button is unfolded, no other message is shown
    await contains(`${STEPS_BUTTON_SELECTOR} i[data-icon='expand_more']`);
    await contains(RESPONSE_SELECTOR, { count: 0 });
    await contains(PREVIEW_SELECTOR, { count: 0 });
    await contains(TOOL_STATUS_SELECTOR);
    // tool status is not a button anymore, just a text showing the current action
    await contains(`${TOOL_STATUS_SELECTOR}:is(button)`, { count: 0 });
    expect(queryOne(TOOL_STATUS_SELECTOR)).toHaveText("Searching matching leads");

    // clicking on next steps folds the current group again
    await click(STEPS_BUTTON_SELECTOR);
    await contains(STEP_MSG_SELECTOR, { count: 0 });
    await contains(AGENT_HEADER_SELECTOR, { count: 0 });
    await contains(STEPS_BUTTON_SELECTOR, { count: 0 });
    await contains(RESPONSE_SELECTOR, { count: 0 });
    await contains(PREVIEW_SELECTOR, { count: 0 });
    await contains(TOOL_STATUS_SELECTOR, { count: 1 });
    await contains(`${TOOL_STATUS_SELECTOR}:is(button)`);

    pyEnv["bus.bus"]._sendone(
        pyEnv["discuss.channel"].browse(channelId)[0],
        "mail.record/insert",
        new Store()
            .add(pyEnv["ai.session"].browse(sessionId), { loop_state: "ready", toolStatus: false })
            .as_dict(),
    );
    await contains(TOOL_STATUS_SELECTOR, { count: 0 });
});

test("toggle-agent-steps action is shown", async () => {
    const pyEnv = await startServer();
    const agentPartnerId = pyEnv["res.partner"].create({ name: "Agent Partner" });
    const agentId = pyEnv["ai.agent"].create({
        name: "Agent Partner",
        partner_id: agentPartnerId,
    });
    const { channelId } = createAIChat(pyEnv, agentId);

    await start();
    await openDiscuss(channelId);
    await click(".o-mail-Composer button[title='More Actions']");
    await contains(".o-dropdown-item[name='toggle-agent-steps']", { text: "Show Steps" });
});
