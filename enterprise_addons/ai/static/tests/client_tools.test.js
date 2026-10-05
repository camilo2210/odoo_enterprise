import { aiSessionIdentifier } from "@ai/utils/ai_session_identifier";
import { runOneWayClientToolBatch } from "@ai/discuss/core/common/ai_client_tool_service";
import {
    click,
    contains,
    insertText,
    setupChatHub,
    start,
    startServer,
} from "@mail/../tests/mail_test_helpers";
import { before, beforeEach, describe, expect, test } from "@odoo/hoot";
import { press } from "@odoo/hoot-dom";
import {
    Command,
    MockServer,
    getService,
    mockService,
    onRpc,
    serverState,
} from "@web/../tests/web_test_helpers";
import { registry } from "@web/core/registry";
import { defineAIModels } from "./ai_test_helpers";

describe.current.tags("desktop");
defineAIModels();

/**
 * Registers an AI tool for the duration of the current test.
 * The tool is added before the test runs and removed after.
 *
 * @param {string} name
 * @param {(thread, params) => Promise<void>} handler
 */
function withAITool(name, handler) {
    before(() => {
        const aiTools = registry.category("ai.client_tools");
        aiTools.add(name, handler);
        return () => aiTools.remove(name);
    });
}

let channelId, channel;
beforeEach(async () => {
    const pyEnv = await startServer();
    const partnerId = pyEnv["res.partner"].create({ name: "Agent Partner" });
    const aiAgentId = pyEnv["ai.agent"].create({
        name: "Agent Partner",
        partner_id: partnerId,
    });
    channelId = pyEnv["discuss.channel"].create({
        channel_member_ids: [
            Command.create({ partner_id: serverState.partnerId }),
            Command.create({ partner_id: partnerId }),
        ],
        channel_type: "ai_chat",
        ai_agent_id: aiAgentId,
        ai_session_ids: [Command.create({ agent_id: aiAgentId })],
    });
    [channel] = pyEnv["discuss.channel"].search_read([["id", "=", channelId]]);
});

async function postInChatWindow(text) {
    await contains(".o-mail-ChatWindow");
    await click(".o-mail-ChatWindow .o-mail-Composer-input");
    await insertText(".o-mail-ChatWindow .o-mail-Composer-input", text);
    await press("Enter");
}

test("Oneway tool request is dispatched to handler in tool registry", async () => {
    withAITool("dummy_tool", async (thread, params) => {
        expect.step(`dummy_tool:${params.greeting}`);
        expect(thread.id).toBe(channelId);
    });
    onRpc("/ai/start_session_advance", () => {
        expect.step("start session advance");
        return { loop_state: "waiting_model" };
    });
    setupChatHub({ opened: [channelId] });
    await start();
    await postInChatWindow("do the thing");
    await expect.waitForSteps(["start session advance"]);
    MockServer.env["bus.bus"]._sendone(channel, "ai.session/client_tools", {
        channel_id: channelId,
        aiSessionIdentifier,
        commands: [
            {
                name: "dummy_tool",
                params: { greeting: "hello" },
                oneway: true,
            },
        ],
    });
    await expect.waitForSteps(["dummy_tool:hello"]);
});

test("Client tool result is sent in a follow-up request", async () => {
    const [sessionId] = MockServer.env["ai.session"].search([["channel_id", "=", channelId]]);
    const resumeToken = "client-result-token";
    withAITool("get_client_data", async (thread, params) => {
        expect.step(`get_client_data:${params.key}`);
        expect(thread.id).toBe(channelId);
        return { clientValue: 42 };
    });
    onRpc("/ai/start_session_advance", async (request) => {
        const { params } = await request.json();
        expect("response" in params).toBe(false);
        expect(params.ai_session_identifier).toBe(aiSessionIdentifier);
        expect.step("start session advance");
        return { loop_state: "waiting_model" };
    });
    onRpc("/ai/resume_pending_interaction", async (request) => {
        const { params } = await request.json();
        expect(params.channel_id).toBe(channelId);
        expect(params.ai_session_identifier).toBe(aiSessionIdentifier);
        expect(params.session_id).toBe(sessionId);
        expect(params.resume_token).toBe(resumeToken);
        expect("mail_message_id" in params).toBe(false);
        expect(params.response).toEqual({
            kind: "client_result",
            value: { clientValue: 42 },
        });
        expect.step("client result submitted");
        return { loop_state: "waiting_model" };
    });
    setupChatHub({ opened: [channelId] });
    await start();
    await postInChatWindow("get client data");
    await expect.waitForSteps(["start session advance"]);
    MockServer.env["bus.bus"]._sendone(channel, "mail.record/insert", {
        "ai.session": [
            {
                id: sessionId,
                loop_state: "waiting_client_result",
                clientToolRequest: {
                    aiSessionIdentifier,
                    name: "get_client_data",
                    params: { key: "value" },
                    resumeToken,
                },
            },
        ],
    });
    await expect.waitForSteps(["get_client_data:value", "client result submitted"]);
});

test("Client tool error is sent in a follow-up request", async () => {
    const [sessionId] = MockServer.env["ai.session"].search([["channel_id", "=", channelId]]);
    const resumeToken = "client-error-token";
    withAITool("get_client_data", async () => {
        expect.step("get_client_data");
        throw new Error("Client tool failed");
    });
    onRpc("/ai/start_session_advance", () => {
        expect.step("start session advance");
        return { loop_state: "waiting_model" };
    });
    onRpc("/ai/resume_pending_interaction", async (request) => {
        const { params } = await request.json();
        expect(params.channel_id).toBe(channelId);
        expect(params.ai_session_identifier).toBe(aiSessionIdentifier);
        expect(params.session_id).toBe(sessionId);
        expect(params.resume_token).toBe(resumeToken);
        expect("mail_message_id" in params).toBe(false);
        expect(params.response).toEqual({
            kind: "client_error",
            value: "Client tool failed",
        });
        expect.step("client error submitted");
        return { loop_state: "waiting_model" };
    });
    setupChatHub({ opened: [channelId] });
    await start();
    await postInChatWindow("get client data");
    await expect.waitForSteps(["start session advance"]);
    MockServer.env["bus.bus"]._sendone(channel, "mail.record/insert", {
        "ai.session": [
            {
                id: sessionId,
                loop_state: "waiting_client_result",
                clientToolRequest: {
                    aiSessionIdentifier,
                    name: "get_client_data",
                    params: {},
                    resumeToken,
                },
            },
        ],
    });
    await expect.waitForSteps(["get_client_data", "client error submitted"]);
});

test("Reload runs once after oneway tools", async () => {
    withAITool("first_tool", async () => expect.step("first"));
    mockService("action", {
        doAction(action) {
            expect(action.tag).toBe("soft_reload");
            expect.step("reload");
        },
    });
    onRpc("/ai/start_session_advance", () => {
        expect.step("start session advance");
        return { loop_state: "waiting_model" };
    });
    setupChatHub({ opened: [channelId] });
    await start();
    await postInChatWindow("do the thing");
    await expect.waitForSteps(["start session advance"]);
    MockServer.env["bus.bus"]._sendone(channel, "ai.session/client_tools", {
        channel_id: channelId,
        aiSessionIdentifier,
        commands: [
            { name: "reload", oneway: true },
            { name: "reload", oneway: true },
            { name: "first_tool", oneway: true },
        ],
    });
    await expect.waitForSteps(["first", "reload"]);
});

test("Reload without oneway sends its result in a follow-up request", async () => {
    const [sessionId] = MockServer.env["ai.session"].search([["channel_id", "=", channelId]]);
    const resumeToken = "reload-result-token";
    mockService("action", {
        doAction(action) {
            expect(action.tag).toBe("soft_reload");
            expect.step("reload");
        },
    });
    onRpc("/ai/start_session_advance", () => {
        expect.step("start session advance");
        return { loop_state: "waiting_model" };
    });
    onRpc("/ai/resume_pending_interaction", async (request) => {
        const { params } = await request.json();
        expect(params.channel_id).toBe(channelId);
        expect(params.ai_session_identifier).toBe(aiSessionIdentifier);
        expect(params.session_id).toBe(sessionId);
        expect(params.resume_token).toBe(resumeToken);
        expect("mail_message_id" in params).toBe(false);
        expect(params.response).toEqual({
            kind: "client_result",
            value: "Success",
        });
        expect.step("reload result submitted");
        return { loop_state: "waiting_model" };
    });
    setupChatHub({ opened: [channelId] });
    await start();
    await postInChatWindow("reload");
    await expect.waitForSteps(["start session advance"]);
    MockServer.env["bus.bus"]._sendone(channel, "mail.record/insert", {
        "ai.session": [
            {
                id: sessionId,
                loop_state: "waiting_client_result",
                clientToolRequest: {
                    aiSessionIdentifier,
                    name: "reload",
                    params: {},
                    resumeToken,
                },
            },
        ],
    });
    await expect.waitForSteps(["reload", "reload result submitted"]);
});

test("Client tools only execute and submit results in the requesting tab", async () => {
    const [sessionId] = MockServer.env["ai.session"].search([["channel_id", "=", channelId]]);
    withAITool("dummy_tool", async () => expect.step("oneway executed"));
    withAITool("get_client_data", async () => {
        expect.step("pending executed");
        return "result";
    });
    onRpc("/ai/resume_pending_interaction", async (request) => {
        const { params } = await request.json();
        expect(params.ai_session_identifier).toBe(aiSessionIdentifier);
        expect(params.response).toEqual({ kind: "client_result", value: "result" });
        expect.step("result submitted");
        return { loop_state: "ready" };
    });
    setupChatHub({ opened: [channelId] });
    await start();
    const store = getService("mail.store");
    const session = store["ai.session"].get(sessionId);
    const payload = {
        channel_id: channelId,
        aiSessionIdentifier: "another-tab",
        commands: [{ name: "dummy_tool", params: {}, oneway: true }],
    };
    const request = {
        aiSessionIdentifier: "another-tab",
        name: "get_client_data",
        params: {},
        resumeToken: "same-command",
    };

    await runOneWayClientToolBatch(store, payload);
    session.clientToolRequest = request;
    await session.processPendingClientTool();
    expect.verifySteps([]);

    await runOneWayClientToolBatch(store, { ...payload, aiSessionIdentifier });
    session.clientToolRequest = { ...request, aiSessionIdentifier };
    await expect.waitForSteps(["oneway executed", "pending executed", "result submitted"]);
});
