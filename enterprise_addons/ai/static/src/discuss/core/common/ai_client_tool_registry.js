import { markup } from "@odoo/owl";
import { registry } from "@web/core/registry";

/** Registry of browser-side tools that an AI session can invoke. */
export const aiClientToolsRegistry = registry.category("ai.client_tools");

export async function runAiClientTool(thread, { name, params }) {
    const tool = aiClientToolsRegistry.get(name, null);
    if (!tool) {
        throw new Error(`Unknown AI client tool: ${name}`);
    }
    if (name === "show_view" && params?.action?.help) {
        params.action.help = markup(params.action.help);
    }
    return await tool(thread, params);
}
