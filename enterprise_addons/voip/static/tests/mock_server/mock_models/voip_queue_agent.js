import { models } from "@web/../tests/web_test_helpers";

export class VoipQueueAgent extends models.ServerModel {
    _name = "voip.queue.agent";

    get_current_user_queue_memberships() {
        return [];
    }

    set_current_user_queue_membership(agentId, isLogged) {
        this.write([agentId], { is_logged: isLogged });
        return isLogged;
    }
}
