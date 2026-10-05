import { aiSessionIdentifier } from "@ai/utils/ai_session_identifier";
import { runAiClientTool } from "@ai/discuss/core/common/ai_client_tool_registry";

import { registry } from "@web/core/registry";

export async function runOneWayClientToolBatch(store, payload) {
    if (payload.aiSessionIdentifier !== aiSessionIdentifier) {
        return;
    }
    const commands = payload.commands;
    const thread = store["mail.thread"].get({
        id: payload.channel_id,
        model: "discuss.channel",
    });
    if (!thread) {
        return;
    }

    let reloadCommand;
    for (const command of commands) {
        if (command.name === "reload") {
            reloadCommand = command;
            continue;
        }
        try {
            await runAiClientTool(thread, command);
        } catch (error) {
            console.warn(`Could not run AI client tool ${command.name}: ${error.message}`);
        }
    }
    if (reloadCommand) {
        try {
            await runAiClientTool(thread, reloadCommand);
        } catch (error) {
            console.warn(`Could not run AI client tool reload: ${error.message}`);
        }
    }
}

export const aiClientToolBusService = {
    dependencies: ["bus_service", "mail.store"],
    start(_env, services) {
        services.bus_service.subscribe("ai.session/client_tools", async (payload) => {
            await runOneWayClientToolBatch(services["mail.store"], payload);
        });
    },
};

registry.category("services").add("ai.client_tools", aiClientToolBusService);
