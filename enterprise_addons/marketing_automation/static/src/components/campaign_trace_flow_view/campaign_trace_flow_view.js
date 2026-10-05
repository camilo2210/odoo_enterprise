import { _t } from "@web/core/l10n/translation";
import { Component, markup, onWillStart, t, useProps } from "@odoo/owl";
import { FlowViewMixin } from "@marketing_automation/components/flow_view_mixin/flow_view_mixin";
import { MarketingDomainSelector } from "@marketing_automation/components/domain_selector/domain_selector";
import { deserializeDateTime, formatDateTime } from "@web/core/l10n/dates";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { useService } from "@web/core/utils/hooks";

export class CampaignTraceFlowView extends FlowViewMixin(Component) {
    static template = "marketing_automation.CampaignTraceFlowView";
    static components = {
        DomainSelector: MarketingDomainSelector,
    };
    props = useProps({
        ...standardWidgetProps,
        record: t.object().optional(),
    });

    /** @override */
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.action = useService("action");
        onWillStart(() => this.load());
    }

    /** @returns {Object} */
    get record() {
        return this.state.record;
    }

    /** @returns {Object} */
    get specification() {
        return {
            campaign_id: {
                // marketing.campaign
                fields: {
                    model_id: {
                        // ir.model
                        fields: {
                            display_name: {},
                        },
                    },
                    model_name: {},
                    enroll_type: {},
                    view_coordinates: {},
                    marketing_activity_ids: {
                        // marketing.activity
                        fields: {
                            name: {},
                            interval_number: {},
                            interval_type: {},
                            activity_domain: {},
                            parent_id: {},
                            activity_type: {},
                            mass_mailing_id: {
                                // mailing.mailing
                                fields: {
                                    display_name: {},
                                },
                            },
                            model_name: {},
                            trigger_type: {},
                            split_domain: {},
                            wait_value_domain: {},
                            is_split_no: {},
                            description: {},
                            view_coordinates: {},
                            trigger_type_ui: {},
                            triggering_activity_id: {
                                fields: {
                                    display_name: {},
                                },
                            },
                            server_action_state: {},
                            server_action_id: {
                                fields: {
                                    display_name: {},
                                },
                            },
                            child_ids: {},
                        },
                    },
                },
            },
            create_date: {},
            trace_ids: {
                // marketing.trace
                fields: {
                    activity_id: {},
                    state: {},
                    schedule_date: {},
                    mailing_trace_ids: {
                        // mailing.trace
                        fields: {
                            sent_datetime: {},
                            open_datetime: {},
                            reply_datetime: {},
                            links_click_datetime: {},
                            trace_status: {},
                        },
                    },
                },
            },
        };
    }

    /**
     * @param {Object} trace
     * @returns {boolean}
     */
    hasProcessedDelay(trace) {
        return trace.state !== "scheduled";
    }

    /**
     * @param {Object} trace
     * @returns {boolean}
     */
    hasProcessedActivityTrigger(trace) {
        return trace.schedule_date !== false;
    }

    /**
     * @param {Object} activity
     * @returns {string}
     */
    getDomainDisplay(activity) {
        return (
            (activity.activity_type === "split" || activity.trigger_type === "wait_value"
                ? activity.split_domain || activity.wait_value_domain || "[]"
                : activity.activity_domain) || "[]"
        );
    }

    /**
     * @param {Object} activity
     * @returns {string}
     */
    getActivityTriggerDescription(activity) {
        if (activity.trigger_type === "mail_open") {
            const triggeringActivity = this.getTriggeringMarketingActivity(activity);
            return _t(`Opened "%(mail)s"`, {
                mail: triggeringActivity?.mass_mailing_id.display_name,
            });
        }
        if (activity.trigger_type === "mail_not_open") {
            const triggeringActivity = this.getTriggeringMarketingActivity(activity);
            return _t(`Didn't open "%(mail)s"`, {
                mail: triggeringActivity?.mass_mailing_id.display_name,
            });
        }
        if (activity.trigger_type === "mail_reply") {
            const triggeringActivity = this.getTriggeringMarketingActivity(activity);
            return _t(`Replied to "%(mail)s"`, {
                mail: triggeringActivity?.mass_mailing_id.display_name,
            });
        }
        if (activity.trigger_type === "mail_not_reply") {
            const triggeringActivity = this.getTriggeringMarketingActivity(activity);
            return _t(`Didn't reply to "%(mail)s"`, {
                mail: triggeringActivity?.mass_mailing_id.display_name,
            });
        }
        if (activity.trigger_type === "mail_click") {
            const triggeringActivity = this.getTriggeringMarketingActivity(activity);
            return _t(`Clicked in "%(mail)s"`, {
                mail: triggeringActivity?.mass_mailing_id.display_name,
            });
        }
        if (activity.trigger_type === "mail_not_click") {
            const triggeringActivity = this.getTriggeringMarketingActivity(activity);
            return _t(`Didn't click in "%(mail)s"`, {
                mail: triggeringActivity?.mass_mailing_id.display_name,
            });
        }
        if (activity.trigger_type === "mail_bounce") {
            const triggeringActivity = this.getTriggeringMarketingActivity(activity);
            return _t(`"%(mail)s" bounced`, {
                mail: triggeringActivity?.mass_mailing_id.display_name,
            });
        }
    }

    /**
     * @param {Object} activity
     * @returns {boolean}
     */
    hasTriggerNode(activity) {
        return (
            activity.activity_type !== "split" &&
            !["activity", "begin", "collect_reply"].includes(activity.trigger_type)
        );
    }

    /**
     * @param {Object} activity
     * @returns {boolean}
     */
    hasDelayNode(activity) {
        return !!activity.interval_number;
    }

    /**
     * @param {Object}
     * @returns {boolean}
     */
    hasActivityNode(activity) {
        return activity.activity_type !== "structure";
    }

    /** @returns {boolean} */
    hasVisibleNode(activity) {
        return (
            this.hasTriggerNode(activity) ||
            this.hasDelayNode(activity) ||
            this.hasActivityNode(activity)
        );
    }

    /** @returns {boolean} */
    hasActivityForTrigger() {
        return this.record.campaign_id.marketing_activity_ids.find(
            (current) => !current.parent_id && current.trigger_type !== "collect_reply"
        );
    }

    /** @returns {boolean} */
    hasActivityForReplyTrigger() {
        return this.record.campaign_id.marketing_activity_ids.find(
            (current) => !current.parent_id && current.trigger_type === "collect_reply"
        );
    }

    /**
     * @param {Object} campaign
     * @returns {{ x: double, y: double }}
     */
    getTriggerPositionOnScreen(campaign) {
        const position = {
            x: campaign.view_coordinates?.trigger?.x || 0,
            y: campaign.view_coordinates?.trigger?.y || 0,
        };
        return this.transform(position.x, position.y);
    }

    /**
     * @param {Object} campaign
     * @returns {{ x: double, y: double }}
     */
    getTriggerFlagPositionOnScreen(campaign) {
        const position = {
            x: campaign.view_coordinates?.trigger_flag?.x || 0,
            y: campaign.view_coordinates?.trigger_flag?.y || 0,
        };
        return this.transform(position.x, position.y);
    }

    /**
     * @param {Object} campaign
     * @returns {{ x: double, y: double }}
     */
    getReplyTriggerPositionOnScreen(campaign) {
        const position = {
            x: campaign.view_coordinates?.reply_trigger?.x || 0,
            y: campaign.view_coordinates?.reply_trigger?.y || 0,
        };
        return this.transform(position.x, position.y);
    }

    /**
     * @param {Object} activity
     * @returns {{ x: double, y: double }}
     */
    getActivityPositionOnScreen(activity) {
        const position = {
            x: activity.view_coordinates?.activity?.x || 0,
            y: activity.view_coordinates?.activity?.y || 0,
        };
        return this.transform(position.x, position.y);
    }

    /**
     * @param {Object} activity
     * @returns {{ x: double, y: double }}
     */
    getActivityTriggerPositionOnScreen(activity) {
        const position = {
            x: activity.view_coordinates?.trigger?.x || 0,
            y: activity.view_coordinates?.trigger?.y || 0,
        };
        return this.transform(position.x, position.y);
    }

    /**
     * @param {Object} activity
     * @returns {{ x: double, y: double }}
     */
    getActivityDelayPositionOnScreen(activity) {
        const position = {
            x: activity.view_coordinates?.delay?.x || 0,
            y: activity.view_coordinates?.delay?.y || 0,
        };
        return this.transform(position.x, position.y);
    }

    /**
     * @param {Object} activity
     * @returns {{ x: double, y: double }}
     */
    getActivityFlagPositionOnScreen(activity) {
        const position = {
            x: activity.view_coordinates?.flag?.x || 0,
            y: activity.view_coordinates?.flag?.y || 0,
        };
        return this.transform(position.x, position.y);
    }

    /**
     * @param {Object} activity
     * @returns {{ x: double, y: double }}
     */
    getYesBranchPositionOnScreen(activity) {
        const position = {
            x: activity.view_coordinates?.yes_branch_flag?.x || 0,
            y: activity.view_coordinates?.yes_branch_flag?.y || 0,
        };
        return this.transform(position.x, position.y);
    }

    /**
     * @param {Object} activity
     * @returns {{ x: double, y: double }}
     */
    getNoBranchPositionOnScreen(activity) {
        const position = {
            x: activity.view_coordinates?.no_branch_flag?.x || 0,
            y: activity.view_coordinates?.no_branch_flag?.y || 0,
        };
        return this.transform(position.x, position.y);
    }

    /**
     * @param {Object} activity
     * @returns {Object}
     */
    getParentMarketingActivity(activity) {
        return this.record.campaign_id.marketing_activity_ids.find(
            (current) => current.id === activity.parent_id
        );
    }

    /**
     * @param {Object} activity
     * @returns {Array[Object]}
     */
    getChildrenMarketingActivity(activity) {
        return this.record.campaign_id.marketing_activity_ids.filter(
            (current) => current.parent_id === activity.id
        );
    }

    /**
     * @param {Object} activity
     * @returns {Object}
     */
    getMarketingActivityTrace(activity) {
        return this.record.trace_ids.find((trace) => trace.activity_id === activity.id);
    }

    /**
     * @param {Object}
     * @returns {Object}
     */
    getTriggeringMarketingActivity(activity) {
        return this.record.campaign_id.marketing_activity_ids.find(
            (current) => current.id === activity.triggering_activity_id.id
        );
    }

    /**
     * @param {Record} activity
     * @returns {{ x: double, y: double }}
     */
    getPositionOfFirstVisibleNodeOnScreen(activity) {
        if (this.hasTriggerNode(activity)) {
            return this.getActivityTriggerPositionOnScreen(activity);
        }
        if (this.hasDelayNode(activity)) {
            return this.getActivityDelayPositionOnScreen(activity);
        }
        if (this.hasActivityNode(activity)) {
            return this.getActivityPositionOnScreen(activity);
        }
        throw new Error("No node for the activity", activity);
    }

    /**
     * @param {Record} activity
     * @returns {{ x: double, y: double }}
     */
    getPositionOfLastVisibleNodeOnScreen(activity) {
        let current = activity;
        while (current) {
            if (this.hasActivityNode(current)) {
                return this.getActivityPositionOnScreen(current);
            }
            if (this.hasDelayNode(current)) {
                return this.getActivityDelayPositionOnScreen(current);
            }
            if (this.hasTriggerNode(current)) {
                return this.getActivityTriggerPositionOnScreen(current);
            }
            const parent = this.getParentMarketingActivity(current);
            if (!parent) {
                if (current.trigger_type === "collect_reply") {
                    return this.getReplyTriggerPositionOnScreen(this.record);
                } else {
                    return this.getTriggerPositionOnScreen(this.record);
                }
            }
            current = parent;
        }
        return this.getTriggerPositionOnScreen(this.record);
    }

    /**
     * @param {string} date
     * @returns {string}
     */
    formatDate(date) {
        if (!date) {
            return _t("a future date.");
        }
        return formatDateTime(deserializeDateTime(date), { format: "MMM d, h:mm a" });
    }

    /**
     * @param {Object} activity
     * @param {Event} e1
     */
    async addPointerListenerOnMarketingActivity(activity, e1) {
        /** @param {Event} e2 */
        const onMarketingActivityClick = async (e2) => {
            const trace = this.getMarketingActivityTrace(activity);
            if (trace) {
                await this.action.doAction({
                    name: _t("Marketing Trace"),
                    type: "ir.actions.act_window",
                    res_model: "marketing.trace",
                    res_id: trace.id,
                    views: [[false, "form"]],
                    target: "new",
                });
            }
        };
        this.addPointerListeners(
            e1,
            onMarketingActivityClick,
            (e2) => {
                e2.stopPropagation();
            },
            (e2) => {
                e2.stopPropagation();
            }
        );
    }

    /**
     * @param {Object} trace
     * @param {Event} e1
     */
    async addPointerListenerOnExecuteStepBtn(trace, e1) {
        e1.stopPropagation();
        /** @param {Event} e2 */
        const onExecuteStepBtnClick = async (e2) => {
            e2.stopPropagation();
            await this.orm.call("marketing.trace", "action_execute", [trace.id]);
            await this.refresh();
        };
        this.addPointerListeners(
            e1,
            onExecuteStepBtnClick,
            (e2) => {
                e2.stopPropagation();
            },
            (e2) => {
                e2.stopPropagation();
            }
        );
    }

    /**
     * @param {Object} trace
     * @param {Event} e1
     */
    async addPointerListenerOnCancelStepBtn(trace, e1) {
        e1.stopPropagation();
        /** @param {Event} e2 */
        const onCancelStepBtnClick = async (e2) => {
            e2.stopPropagation();
            await this.orm.call("marketing.trace", "action_set_canceled_manual", [trace.id]);
            await this.refresh();
        };
        this.addPointerListeners(
            e1,
            onCancelStepBtnClick,
            (e2) => {
                e2.stopPropagation();
            },
            (e2) => {
                e2.stopPropagation();
            }
        );
    }

    async load() {
        const [record] = await this.orm.webRead(
            "marketing.participant",
            [this.props.record.resId],
            {
                specification: this.specification,
            }
        );
        record.campaign_id.marketing_activity_ids.forEach(
            (activity) => (activity.description = markup(activity.description || ""))
        );
        this.state.record = record;
    }

    async refresh() {
        await this.props.record.model.load({ resId: this.props.record.resId });
        await this.load();
    }
}

export const campaignTraceFlowView = {
    component: CampaignTraceFlowView,
};

registry.category("view_widgets").add("campaign_trace_flow_view", campaignTraceFlowView);
