import { usePlugin } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { NotificationPlugin } from "@web/core/notifications/notification_plugin";
import { CampaignFlowView } from "@marketing_automation/components/campaign_flow_view/campaign_flow_view";

patch(CampaignFlowView.prototype, {
    setup() {
        super.setup();
        this.notification = usePlugin(NotificationPlugin);
        this.launcher = useService("aiChatLauncher");
    },

    async onAiChatClick() {
        if (!this.launcher) {
            this.notification.add(_t("AI service not available."), { type: "warning" });
            return;
        }
        try {
            const [campaignId] = await this.orm.create("marketing.campaign", [
                { title: _t("Campaign") },
            ]);
            this.refresh({ resId: campaignId });
            const res = await this.launcher.launchAIChat({
                interfaceKey: "campaign_builder_ai",
                channelTitle: _t("AI Campaign Assistant"),
                recordModel: "marketing.campaign",
                recordId: campaignId,
            });
            console.log(res);
        } catch (e) {
            this.notification.add(_t("Failed to open AI chat."), { type: "danger" });
            console.error(e);
        }
    },
});
