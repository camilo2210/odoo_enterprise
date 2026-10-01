import {
    click,
    contains,
    insertText,
    setupChatHub,
    start,
    startServer,
} from "@mail/../tests/mail_test_helpers";

import { describe, expect, test } from "@odoo/hoot";
import { press } from "@odoo/hoot-dom";

import { onRpc } from "@web/../tests/web_test_helpers";
import { createAIChat, defineAIModels } from "../ai_test_helpers";

describe.current.tags("desktop");
defineAIModels();

const COMPOSER_SELECTOR = ".o-mail-Composer";
const INPUT_REQUEST_SELECTOR = ".o_ai_user_input_request";
const EXTERNAL_WAIT_SELECTOR = ".o_ai_external_pending_tool";

async function startAIChat(sessionValues, messageBodies = ["What should I do?"]) {
    const pyEnv = await startServer();
    const agentPartnerId = pyEnv["res.partner"].create({ name: "AI Agent" });
    const agentId = pyEnv["ai.agent"].create({
        name: "AI Agent",
        partner_id: agentPartnerId,
    });
    const { channelId, sessionId } = createAIChat(pyEnv, agentId);
    const userInputRequest = sessionValues.user_input_request;
    if (userInputRequest) {
        sessionValues = {
            loop_state: userInputRequest.type === "confirmation" ? "waiting_confirmation" : "waiting_answer",
            ...sessionValues,
            user_input_request: {
                resumeToken: "durable-user-input-token",
                ...userInputRequest,
            },
        };
    }
    pyEnv["ai.session"].write([sessionId], sessionValues);
    for (const body of messageBodies) {
        pyEnv["mail.message"].create({
            author_id: agentPartnerId,
            body,
            message_type: "comment",
            model: "discuss.channel",
            res_id: channelId,
        });
    }
    setupChatHub({ opened: [channelId] });
    await start();
    await contains(".o-mail-ChatWindow");
    return { channelId, sessionId, pyEnv };
}

test("request is rendered once separately from AI messages", async () => {
    await startAIChat(
        {
            user_input_request: {
                choices: [
                    { label: "One", value: "one" },
                    { label: "Two", value: "two" },
                ],
                multiSelect: false,
                type: "question",
            },
        },
        ["Older AI message", "Newest AI message"],
    );

    await contains(".o-mail-Message", { count: 2 });
    await contains(INPUT_REQUEST_SELECTOR, { count: 1 });
    await contains(`.o-mail-Message ${INPUT_REQUEST_SELECTOR}`, { count: 0 });
    await contains(".o-mail-Message:has(:text('Newest AI message')) .o-mail-Message-actions", {
        count: 0,
    });
    await contains(".o-mail-Message:has(:text('Older AI message')) .o-mail-Message-actions");
});

test("pending external tool freezes the composer while showing a progress indicator", async () => {
    await startAIChat(
        {
            external_pending_tool: true,
            loop_state: "waiting_external_result",
            resume_token: "durable-external-tool-token",
        },
        ["Older AI message", "The external task has started."],
    );

    await contains(EXTERNAL_WAIT_SELECTOR, { count: 1 });
    await contains(
        `.o-mail-Message:has(:text('The external task has started.')) ${EXTERNAL_WAIT_SELECTOR} .oi-spin`
    );
    await contains(INPUT_REQUEST_SELECTOR, { count: 0 });
    await contains(COMPOSER_SELECTOR, { count: 0 });
    // Cancel is the only way out of a wait whose external result never arrives.
    await contains(`${EXTERNAL_WAIT_SELECTOR} .o_ai_cancel_external`);
});

test("cancelling a pending external tool aborts it and frees the composer", async () => {
    onRpc("/ai/resume_pending_interaction", async (request) => {
        const { params } = await request.json();
        expect(params.channel_id).toBe(channelId);
        expect(params.session_id).toBe(sessionId);
        expect(params.resume_token).toBe("durable-external-tool-token");
        expect(params.response).toEqual({ kind: "skip" });
        expect.step("pending tools aborted");
        return { loop_state: "ready", interactionConsumed: true };
    });
    const { channelId, sessionId } = await startAIChat(
        {
            external_pending_tool: true,
            loop_state: "waiting_external_result",
            resume_token: "durable-external-tool-token",
        },
        ["The external task has started."],
    );

    await click(`${EXTERNAL_WAIT_SELECTOR} .o_ai_cancel_external`);
    await expect.waitForSteps(["pending tools aborted"]);
    await contains(EXTERNAL_WAIT_SELECTOR, { count: 0 });
    // the composer is usable again, so the chat is not frozen on a dead wait
    await contains(COMPOSER_SELECTOR);
});

test("single choice submits the question answer and hides the choices", async () => {
    onRpc("/ai/resume_pending_interaction", async (request) => {
        const { params } = await request.json();
        expect(params.response).toEqual({
            kind: "question",
            value: ["draft"],
        });
        expect(params.resume_token).toBe("durable-user-input-token");
        expect.step("answer submitted");
        return { loop_state: "waiting_model" };
    });
    await startAIChat({
        user_input_request: {
            choices: [
                { label: "Create a draft", value: "draft" },
                { label: "Send it now", value: "send" },
            ],
            multiSelect: false,
            allowFreeText: true,
            type: "question",
        },
    });

    await contains(`${INPUT_REQUEST_SELECTOR} button:contains('Create a draft')`);
    await contains(`${INPUT_REQUEST_SELECTOR} button:contains('Send it now')`);
    await contains(`${INPUT_REQUEST_SELECTOR} input[placeholder='Something else']`);
    await contains(".o-mail-Message-actions", { count: 0 });
    // the composer is hidden while a question is pending
    await contains(COMPOSER_SELECTOR, { count: 0 });

    await click(`${INPUT_REQUEST_SELECTOR} button:contains('Create a draft')`);
    await expect.waitForSteps(["answer submitted"]);
    await contains(INPUT_REQUEST_SELECTOR, { count: 0 });
    await contains(COMPOSER_SELECTOR);
    await contains(".o-mail-Message-actions");
});

test("free text submits the question answer with the typed value", async () => {
    onRpc("/ai/resume_pending_interaction", async (request) => {
        const { params } = await request.json();
        expect(params.response).toEqual({
            kind: "question",
            value: ["Neither, cancel it"],
        });
        expect.step("answer submitted");
        return { loop_state: "waiting_model" };
    });
    await startAIChat({
        user_input_request: {
            choices: [
                { label: "Create a draft", value: "draft" },
                { label: "Send it now", value: "send" },
            ],
            multiSelect: false,
            allowFreeText: true,
            type: "question",
        },
    });

    await insertText(
        `${INPUT_REQUEST_SELECTOR} input[placeholder='Something else']`,
        "Neither, cancel it",
    );
    await press("Enter");
    await expect.waitForSteps(["answer submitted"]);
    await contains(INPUT_REQUEST_SELECTOR, { count: 0 });
});

test("multi-select submits selected values in choice order", async () => {
    onRpc("/ai/resume_pending_interaction", async (request) => {
        const { params } = await request.json();
        expect(params.response).toEqual({
            kind: "question",
            value: ["first", "third"],
        });
        expect.step("multi-select submitted");
        return { loop_state: "waiting_model" };
    });
    await startAIChat({
        user_input_request: {
            choices: [
                { label: "First", value: "first" },
                { label: "Second", value: "second" },
                { label: "Third", value: "third" },
            ],
            multiSelect: true,
            type: "question",
        },
    });

    await contains(`${INPUT_REQUEST_SELECTOR} button:contains('Confirm'):disabled`);
    await click(`${INPUT_REQUEST_SELECTOR} button:contains('Third')`);
    await click(`${INPUT_REQUEST_SELECTOR} button:contains('First')`);
    await click(`${INPUT_REQUEST_SELECTOR} button:contains('Confirm'):enabled`);
    await expect.waitForSteps(["multi-select submitted"]);
    await contains(INPUT_REQUEST_SELECTOR, { count: 0 });
});

test("skip resumes the durable request without an answer", async () => {
    onRpc("/ai/resume_pending_interaction", async (request) => {
        const { params } = await request.json();
        expect(params.response).toEqual({ kind: "skip" });
        expect(params.resume_token).toBe("durable-user-input-token");
        expect.step("question skipped");
        return { loop_state: "ready" };
    });
    await startAIChat({
        user_input_request: {
            choices: [
                { label: "Create a draft", value: "draft" },
                { label: "Send it now", value: "send" },
            ],
            multiSelect: false,
            type: "question",
        },
    });

    await contains(`${INPUT_REQUEST_SELECTOR} button:contains('Skip')`);
    await click(`${INPUT_REQUEST_SELECTOR} button:contains('Skip')`);
    await expect.waitForSteps(["question skipped"]);
    await contains(INPUT_REQUEST_SELECTOR, { count: 0 });
});
