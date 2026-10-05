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
        if (activity.data.trigger_type === "sms_click") {
            const triggeringActivity = this.getTriggeringMarketingActivity(activity);
            return _t(`Clicked in "%(sms)s"`, {
                sms: triggeringActivity?.data.mass_mailing_id.display_name,
            });
        }
        if (activity.data.trigger_type === "sms_not_click") {
            const triggeringActivity = this.getTriggeringMarketingActivity(activity);
            return _t(`Didn't click in "%(sms)s"`, {
                sms: triggeringActivity?.data.mass_mailing_id.display_name,
            });
        }
        if (activity.data.trigger_type === "sms_bounce") {
            const triggeringActivity = this.getTriggeringMarketingActivity(activity);
            return _t(`"%(sms)s" bounced`, {
                sms: triggeringActivity?.data.mass_mailing_id.display_name,
            });
        }
        return super.getActivityTriggerDescription(activity);
    },
});
