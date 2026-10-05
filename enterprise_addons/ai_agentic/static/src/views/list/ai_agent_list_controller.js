import { ListController } from "@web/views/list/list_controller";

export class AiAgentListController extends ListController {
    /** Create a blank agent and open its chat. */
    async createRecord() {
        await this.actionService.doAction("ai_agentic.ai_agent_action_create");
    }
}
