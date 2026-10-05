import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";

export default class SystrayAction extends Component {
    static template = "ai.SystrayAction";

    setup() {
        super.setup();
        this.actionService = useService("action");
        this.aiChatLauncher = useService("aiChatLauncher");
    }

    async onClickLaunchAIChat() {
        const currentController = this.actionService.currentController;
        if (currentController?.view?.type === "form") {
            this.env.bus.trigger("AI:OPEN_AI_CHAT", { origin: "chatter_ai_button" });
            return;
        }
        this.aiChatLauncher.launchAIChat({
            interfaceKey: "systray_ai_button",
        });
    }
}

registry.category("systray").add(
    "ai.systray_action",
    {
        Component: SystrayAction,
        // A light user has no AI chat: it is not meant to drive the database.
        isDisplayed: () => user.isRegularUser,
    },
    { sequence: 30 }
);
