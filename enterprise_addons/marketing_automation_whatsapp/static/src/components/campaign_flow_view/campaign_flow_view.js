import { _t } from "@web/core/l10n/translation";
import { CampaignFlowView } from "@marketing_automation/components/campaign_flow_view/campaign_flow_view";
import { patch } from "@web/core/utils/patch";

patch(CampaignFlowView.prototype, {
    /**
     * @override
     * @param {Object} activity
     * @returns {string}
     */
    getActivityTriggerDescription(activity) {
        if (activity.data.trigger_type === "whatsapp_click") {
            const triggeringActivity = this.getTriggeringMarketingActivity(activity);
            return _t(`Clicked in "%(whatsapp_message)s"`, {
                whatsapp_message: triggeringActivity?.data.whatsapp_template_id.display_name,
            });
        }
        if (activity.data.trigger_type === "whatsapp_not_click") {
            const triggeringActivity = this.getTriggeringMarketingActivity(activity);
            return _t(`Didn't click in "%(whatsapp_message)s"`, {
                whatsapp_message: triggeringActivity?.data.whatsapp_template_id.display_name,
            });
        }
        if (activity.data.trigger_type === "whatsapp_open") {
            const triggeringActivity = this.getTriggeringMarketingActivity(activity);
            return _t(`Opened "%(whatsapp_message)s"`, {
                whatsapp_message: triggeringActivity?.data.whatsapp_template_id.display_name,
            });
        }
        if (activity.data.trigger_type === "whatsapp_not_open") {
            const triggeringActivity = this.getTriggeringMarketingActivity(activity);
            return _t(`Didn't open "%(whatsapp_message)s"`, {
                whatsapp_message: triggeringActivity?.data.whatsapp_template_id.display_name,
            });
        }
        if (activity.data.trigger_type === "whatsapp_reply") {
            const triggeringActivity = this.getTriggeringMarketingActivity(activity);
            return _t(`Replied to "%(whatsapp_message)s"`, {
                whatsapp_message: triggeringActivity?.data.whatsapp_template_id.display_name,
            });
        }
        if (activity.data.trigger_type === "whatsapp_not_reply") {
            const triggeringActivity = this.getTriggeringMarketingActivity(activity);
            return _t(`Didn't reply to "%(whatsapp_message)s"`, {
                whatsapp_message: triggeringActivity?.data.whatsapp_template_id.display_name,
            });
        }
        if (activity.data.trigger_type === "whatsapp_bounce") {
            const triggeringActivity = this.getTriggeringMarketingActivity(activity);
            return _t(`"%(whatsapp_message)s" bounced`, {
                whatsapp_message: triggeringActivity?.data.whatsapp_template_id.display_name,
            });
        }
        return super.getActivityTriggerDescription(activity);
    },
});
