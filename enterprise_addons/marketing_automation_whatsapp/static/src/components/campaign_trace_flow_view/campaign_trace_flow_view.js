import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { CampaignTraceFlowView } from "@marketing_automation/components/campaign_trace_flow_view/campaign_trace_flow_view";

patch(CampaignTraceFlowView.prototype, {
    /** @override */
    get specification() {
        const spec = super.specification;
        Object.assign(spec.campaign_id.fields.marketing_activity_ids.fields, {
            whatsapp_template_id: {
                fields: {
                    display_name: {},
                },
            },
        });
        return spec;
    },

    /**
     * @override
     * @param {Object} activity
     * @returns {string}
     */
    getActivityTriggerDescription(activity) {
        if (activity.trigger_type === "whatsapp_click") {
            const triggeringActivity = this.getTriggeringMarketingActivity(activity);
            return _t(`Clicked in "%(whatsapp_message)s"`, {
                whatsapp_message: triggeringActivity?.whatsapp_template_id.display_name,
            });
        }
        if (activity.trigger_type === "whatsapp_not_click") {
            const triggeringActivity = this.getTriggeringMarketingActivity(activity);
            return _t(`Didn't click in "%(whatsapp_message)s"`, {
                whatsapp_message: triggeringActivity?.whatsapp_template_id.display_name,
            });
        }
        if (activity.trigger_type === "whatsapp_open") {
            const triggeringActivity = this.getTriggeringMarketingActivity(activity);
            return _t(`Opened "%(whatsapp_message)s"`, {
                whatsapp_message: triggeringActivity?.whatsapp_template_id.display_name,
            });
        }
        if (activity.trigger_type === "whatsapp_not_open") {
            const triggeringActivity = this.getTriggeringMarketingActivity(activity);
            return _t(`Didn't open "%(whatsapp_message)s"`, {
                whatsapp_message: triggeringActivity?.whatsapp_template_id.display_name,
            });
        }
        if (activity.trigger_type === "whatsapp_reply") {
            const triggeringActivity = this.getTriggeringMarketingActivity(activity);
            return _t(`Replied to "%(whatsapp_message)s"`, {
                whatsapp_message: triggeringActivity?.whatsapp_template_id.display_name,
            });
        }
        if (activity.trigger_type === "whatsapp_not_reply") {
            const triggeringActivity = this.getTriggeringMarketingActivity(activity);
            return _t(`Didn't reply to "%(whatsapp_message)s"`, {
                whatsapp_message: triggeringActivity?.whatsapp_template_id.display_name,
            });
        }
        if (activity.trigger_type === "whatsapp_bounce") {
            const triggeringActivity = this.getTriggeringMarketingActivity(activity);
            return _t(`"%(whatsapp_message)s" bounced`, {
                whatsapp_message: triggeringActivity?.whatsapp_template_id.display_name,
            });
        }
        return super.getActivityTriggerDescription(activity);
    },
});
