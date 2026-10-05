import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import SystrayAction from "@ai/web/systray_action";

patch(SystrayAction.prototype, {
    async onClickLaunchAIChat() {
        const controller = await this.actionService.currentController;
        const { resModel, resId } = controller?.props || {};
        if (resModel === "marketing.campaign") {
            this.aiChatLauncher.launchAIChat({
                interfaceKey: "campaign_builder_ai",
                channelTitle: _t("AI Campaign Assistant"),
                recordId: resId || false,
                recordModel: resId ? resModel : false,
            });
            return;
        }
        return super.onClickLaunchAIChat();
    },
});
