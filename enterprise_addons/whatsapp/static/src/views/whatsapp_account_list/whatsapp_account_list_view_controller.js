import { rpc } from "@web/core/network/rpc";
import { ListController } from "@web/views/list/list_controller";

export class WhatsappAccountListController extends ListController {
    setup() {
        super.setup();
        // `create="0"` in the view would hide the import menu too, and manual
        // accounts are created through an import.
        this.activeActions = { ...this.activeActions, create: false };
    }

    async onStartOnboarding() {
        const action = await rpc("/whatsapp/start_onboarding");
        this.actionService.doAction(action);
    }
}
