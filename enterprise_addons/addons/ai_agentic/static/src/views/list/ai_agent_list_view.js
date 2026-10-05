import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { AiAgentListController } from "@ai_agentic/views/list/ai_agent_list_controller";

export const aiAgentListView = {
    ...listView,
    Controller: AiAgentListController,
};

registry.category("views").add("ai_agent_list", aiAgentListView);
