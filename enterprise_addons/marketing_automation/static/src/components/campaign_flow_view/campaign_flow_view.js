import { _t } from "@web/core/l10n/translation";
import { AddStepButton } from "@marketing_automation/components/add_step_button/add_step_button";
import { CampaignSidePanel } from "../campaign_side_panel/campaign_side_panel";
import { CampaignTemplatePickerDialog } from "@marketing_automation/components/campaign_template_picker_dialog/campaign_template_picker_dialog";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { FlowViewMixin } from "@marketing_automation/components/flow_view_mixin/flow_view_mixin";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import { MarketingDomainSelector } from "@marketing_automation/components/domain_selector/domain_selector";
import { MarketingAutomationAddStepPlugin } from "@marketing_automation/plugins/add_step_plugin/add_step_plugin";
import { proxy, useOnChange, useScope, useProps, usePlugin } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { x2ManyField, X2ManyField } from "@web/views/fields/x2many/x2many_field";

export class CampaignFlowView extends FlowViewMixin(X2ManyField) {
    static template = "marketing_automation.CampaignFlowView";
    static components = {
        AddStepButton,
        CampaignSidePanel,
        DomainSelector: MarketingDomainSelector,
    };

    props = useProps();

    TRIGGER_ACTION_TYPES_DISPLAYS = {
        subscribe: _t("Based on Mailing Lists Subscription"),
    };
    SELECTION_DISPLAY_NAME_BACKUP = {
        on_demand: _t("On Demand"),
        date: _t("Based on Date"),
        domain: _t("Based on Conditions"),
        webhook: _t("Based on Webhook"),
    };

    /** @override */
    setup() {
        super.setup();
        this.addStepPlugin = usePlugin(MarketingAutomationAddStepPlugin);
        this.dialog = useService("dialog");
        this.orm = useService("orm");
        this.panelState = proxy(this.env.panelState);
        this.scope = useScope();

        this.coordinates = proxy({
            // Trigger:
            triggers: {},
            replyTriggers: {},
            // Activities:
            activities: {},
            activityTriggers: {},
            activityDelays: {},
            // Flags:
            activityFlags: {},
            triggerFlags: {},
            // Branches:
            yesBranches: {},
            noBranches: {},
            // Forks:
            triggerBranches: {},
            replyTriggerBranches: {},
            activityTriggerBranches: {},
            activityDelayBranches: {},
            activityBranches: {},
        });

        useOnChange(
            () => [this.props.record.resId],
            () => {
                this.state.ready = false;
            }
        );
    }

    // Helpers:

    get canEndEarly() {
        return this.props.record.data.marketing_activity_ids.records.find(
            (current) => current.data.trigger_type === "collect_reply"
        );
    }

    /** @returns {boolean} */
    hasActivityForReplyTrigger() {
        const { records } = this.props.record.data.marketing_activity_ids;
        return records.find(
            (current) => !current.data.parent_id && current.data.trigger_type === "collect_reply"
        );
    }

    /** @returns {boolean} */
    hasActivityForTrigger() {
        const { records } = this.props.record.data.marketing_activity_ids;
        return records.find(
            (current) => !current.data.parent_id && current.data.trigger_type !== "collect_reply"
        );
    }

    /**
     * @param {Object} activity
     * @returns {boolean}
     */
    hasActivityNode(activity) {
        return activity.data.activity_type !== "structure";
    }

    /**
     * @param {Object} activity
     * @returns {boolean}
     */
    hasDelayNode(activity) {
        return !!activity.data.interval_number;
    }

    /**
     * @param {Object} activity
     * @returns {boolean}
     */
    hasTriggerNode(activity) {
        return (
            activity.data.activity_type !== "split" &&
            !["activity", "begin", "collect_reply"].includes(activity.data.trigger_type)
        );
    }

    /**
     * @param {integer} id
     * @returns {Object}
     */
    getMarketingActivity(id) {
        const { records } = this.props.record.data.marketing_activity_ids;
        return records.find((current) => current.id === id);
    }

    /**
     * @param {Object}
     * @returns {Object}
     */
    getTriggeringMarketingActivity(activity) {
        const { records } = this.props.record.data.marketing_activity_ids;
        return records.find(
            (current) => current.resId === activity.data.triggering_activity_id?.id
        );
    }

    /**
     * @param {Object} activity
     * @returns {Object}
     */
    getParentMarketingActivity(activity) {
        const { records } = this.props.record.data.marketing_activity_ids;
        return records.find((current) => current.resId === activity.data.parent_id?.id);
    }

    /**
     * @param {Object} activity
     * @returns {Array[Object]}
     */
    getChildrenMarketingActivity(activity) {
        const { records } = this.props.record.data.marketing_activity_ids;
        return records.filter((current) => current.data.parent_id?.id === activity.resId);
    }

    /** @yields {Array} */
    *getAllPendingBranchesForActivities() {
        // Link for the activity trigger:
        for (const [activityId, position] of Object.entries(
            this.coordinates.activityTriggerBranches
        )) {
            const activity = this.getMarketingActivity(activityId);
            if (activity) {
                const a = this.getActivityTriggerPositionOnScreen(activity);
                const b = this.transform(position.x, position.y);
                yield [a, b, activity, "trigger"];
            }
        }
        // Activity delay:
        for (const [activityId, position] of Object.entries(
            this.coordinates.activityDelayBranches
        )) {
            const activity = this.getMarketingActivity(activityId);
            if (activity) {
                const a = this.getActivityDelayPositionOnScreen(activity);
                const b = this.transform(position.x, position.y);
                yield [a, b, activity, "delay"];
            }
        }
        // Activity:
        for (const [activityId, position] of Object.entries(this.coordinates.activityBranches)) {
            const activity = this.getMarketingActivity(activityId);
            if (activity) {
                const a = this.getActivityPositionOnScreen(activity);
                const b = this.transform(position.x, position.y);
                yield [a, b, activity, false];
            }
        }
    }

    /** @yields {Array} */
    *getAllPendingBranchesForCampaignTriggers() {
        // Campaign trigger:
        for (const position of Object.values(this.coordinates.triggerBranches)) {
            const a = this.getTriggerPositionOnScreen(this.props.record);
            const b = this.transform(position.x, position.y);
            yield [a, b, { trigger_type: "begin" }];
        }
        // Campaign reply trigger:
        for (const position of Object.values(this.coordinates.replyTriggerBranches)) {
            const a = this.getReplyTriggerPositionOnScreen(this.props.record);
            const b = this.transform(position.x, position.y);
            yield [a, b, { trigger_type: "collect_reply" }];
        }
    }

    /**
     * @param {Object} activity
     * @returns {string}
     */
    getActivityTriggerDescription(activity) {
        if (activity.data.trigger_type === "mail_open") {
            const triggeringActivity = this.getTriggeringMarketingActivity(activity);
            return _t(`Opened "%(mail)s"`, {
                mail: triggeringActivity?.data.mass_mailing_id.display_name,
            });
        }
        if (activity.data.trigger_type === "mail_not_open") {
            const triggeringActivity = this.getTriggeringMarketingActivity(activity);
            return _t(`Didn't open "%(mail)s"`, {
                mail: triggeringActivity?.data.mass_mailing_id.display_name,
            });
        }
        if (activity.data.trigger_type === "mail_reply") {
            const triggeringActivity = this.getTriggeringMarketingActivity(activity);
            return _t(`Replied to "%(mail)s"`, {
                mail: triggeringActivity?.data.mass_mailing_id.display_name,
            });
        }
        if (activity.data.trigger_type === "mail_not_reply") {
            const triggeringActivity = this.getTriggeringMarketingActivity(activity);
            return _t(`Didn't reply to "%(mail)s"`, {
                mail: triggeringActivity?.data.mass_mailing_id.display_name,
            });
        }
        if (activity.data.trigger_type === "mail_click") {
            const triggeringActivity = this.getTriggeringMarketingActivity(activity);
            return _t(`Clicked in "%(mail)s"`, {
                mail: triggeringActivity?.data.mass_mailing_id.display_name,
            });
        }
        if (activity.data.trigger_type === "mail_not_click") {
            const triggeringActivity = this.getTriggeringMarketingActivity(activity);
            return _t(`Didn't click in "%(mail)s"`, {
                mail: triggeringActivity?.data.mass_mailing_id.display_name,
            });
        }
        if (activity.data.trigger_type === "mail_bounce") {
            const triggeringActivity = this.getTriggeringMarketingActivity(activity);
            return _t(`"%(mail)s" bounced`, {
                mail: triggeringActivity?.data.mass_mailing_id.display_name,
            });
        }
    }

    /** @returns {string} */
    getCampaignTriggerDescription() {
        if (this.props.record.data["enroll_type"] === "action") {
            return _t("%(model_name)s · %(campaign_trigger_label)s", {
                model_name: this.props.record.data.model_id.display_name,
                campaign_trigger_label:
                    this.TRIGGER_ACTION_TYPES_DISPLAYS[this.props.record.data.enroll_action_type],
            });
        }
        const { fields } = this.props.record.model.config;
        const { selection } = fields["enroll_type"];
        const item = selection.find((item) => item[0] === this.props.record.data["enroll_type"]);
        return _t("%(model_name)s · %(campaign_trigger_label)s", {
            model_name: this.props.record.data.model_id.display_name,
            campaign_trigger_label: item
                ? item[1]
                : this.SELECTION_DISPLAY_NAME_BACKUP[this.props.record.data["enroll_type"]],
        });
    }

    /**
     * @param {Object} activity
     * @returns {string}
     */
    getDomainDisplay(activity) {
        return (
            (activity.data.activity_type === "split" || activity.data.trigger_type === "wait_value"
                ? activity.data.split_domain || activity.data.wait_value_domain
                : activity.data.activity_domain) || "[]"
        );
    }

    // Form view handling:

    async defineTrigger() {
        if (!this.props.record.data.title) {
            await this.props.record.isDirty();
        }
        await this.action.doAction("marketing_automation.marketing_campaign_create_trigger", {
            props: {
                onSave: async (record) => {
                    await this.refresh(record);
                    await this.action.doAction({ type: "ir.actions.act_window_close" });
                },
            },
            additionalContext: {
                default_title: this.props.record.data.title,
            },
        });
    }

    /**
     * @param {string} stepType
     * @param {function} onRecordSave
     */
    async openFormViewToCreateStep(stepType, onRecordSave, additionalContext = {}) {
        const action = await this.orm.call("marketing.campaign", "action_create_step", [
            this.props.record.resId,
            stepType,
        ]);
        if (action) {
            this.addStepPlugin.add(onRecordSave);
            const context = action.context === "{}" ? {} : action.context;
            return this.dialog.add(
                FormViewDialog,
                {
                    resModel: action.res_model,
                    title: _t("Create Step"),
                    viewId: action.view_id[0],
                    context: { ...context, ...additionalContext },
                    onRecordSave,
                },
                { onClose: () => this.addStepPlugin.delete() }
            );
        }
    }

    /**
     * @param {string} stepType
     * @param {integer} activityId
     */
    async openFormViewToEditStep(stepType, activityId) {
        const action = await this.orm.call("marketing.campaign", "action_edit_step", [
            this.props.record.resId,
            stepType,
            activityId,
        ]);
        if (action) {
            await this.props.record.save();
            this.addStepPlugin.add(async () => {
                await this.action.doAction({ type: "ir.actions.act_window_close" });
                return activityId;
            });
            await this.action.doAction(action, {
                props: {
                    /** @param {Object} activity */
                    saveRecord: async (activity) => {
                        await activity.save();
                        await this.action.doAction({ type: "ir.actions.act_window_close" });
                        await this.refresh();
                    },
                    removeRecord: async () => {
                        await this.onDelete(activityId, stepType);
                        await this.action.doAction({ type: "ir.actions.act_window_close" });
                        await this.refresh();
                    },
                    buttonDialogTemplate: "marketing_automation.CampaignFlow.buttonDialogTemplate",
                },
            });
        }
    }

    /**
     * @param {integer} activityId
     * @param {string} stepType
     * @returns {Promise}
     */
    async onDelete(activityId, stepType) {
        /** @returns {Promise} */
        const deleteStep = () => {
            return this.orm.call("marketing.activity", "action_delete_step", [
                activityId,
                stepType,
            ]);
        };
        const openWarningBeforeDeletingStep = () => {
            const close = this.dialog.add(ConfirmationDialog, {
                body: _t("Removing this node will remove all checkpoint nodes that come after it. Are you sure?"),
                confirm: async () => {
                    await deleteStep();
                    close();
                    await this.refresh();
                },
                confirmLabel: _t("Sure"),
                cancelLabel: _t("Cancel"),
            });
        };
        const activity = this.props.record.data.marketing_activity_ids.records.find(
            (rec) => rec.resId === activityId
        );
        if (["begin", "collect_reply"].includes(activity.data.trigger_type)) {
            const isDeletingLastNodeFromMarketingActivity = (
                (stepType === "trigger"
                    && !this.hasDelayNode(activity)
                    && !this.hasActivityNode(activity))
                || (stepType === "delay"
                    && !this.hasTriggerNode(activity)
                    && !this.hasActivityNode(activity))
                || (!["delay", "trigger"].includes(stepType)
                    && !this.hasDelayNode(activity)
                    && !this.hasTriggerNode(activity)));
            if (isDeletingLastNodeFromMarketingActivity) {
                for (const child of this.getChildrenMarketingActivity(activity)) {
                    if (child.data.trigger_type !== "activity") {
                        return openWarningBeforeDeletingStep();
                    }
                }
            }
        };
        return deleteStep();
    }

    // Marketing Campaign Builder

    /**
     * @param {Record} [activity]
     * @param {string} stepType
     * @param {Object} additionalValues
     */
    async addStepAfter(activity, stepType, additionalValues = {}) {
        if (stepType === "branching") {
            let current = activity;
            while (current) {
                if (this.hasActivityNode(current)) {
                    const position = this.getActivityPosition(current);
                    this.coordinates.activityBranches[activity.id] = {
                        x: position.x,
                        y: position.y + 125,
                    };
                    return;
                }
                if (this.hasDelayNode(current)) {
                    const position = this.getActivityDelayPosition(current);
                    this.coordinates.activityDelayBranches[activity.id] = {
                        x: position.x,
                        y: position.y + 125,
                    };
                    return;
                }
                if (this.hasTriggerNode(current)) {
                    const position = this.getActivityTriggerPosition(current);
                    this.coordinates.activityTriggerBranches[activity.id] = {
                        x: position.x,
                        y: position.y + 150,
                    };
                    return;
                }
                const parent = this.getParentMarketingActivity(current);
                if (!parent) {
                    break;
                }
                current = parent;
            }
            const position = this.getTriggerPosition(this.props.record);
            this.coordinates.triggerBranches[this.props.record.id] = {
                x: position.x + 350,
                y: position.y,
            };
            return;
        }
        await this.openFormViewToCreateStep(
            stepType,
            async (record) => {
                if (!(await record.checkValidity({ displayNotification: true }))) {
                    return false;
                }
                if (!this.props.record.resId || this.props.record.isDirty) {
                    await this.props.record.save();
                }
                const values = await this.extractMarketingActivityValues(stepType, record);
                const [res] = await this.orm.call("marketing.campaign", "add_step_after", [
                    this.props.record.resId,
                    stepType,
                    { ...values, ...additionalValues },
                    activity?.resId,
                ]);
                await this.refresh();
                return res;
            },
            Object.fromEntries(
                Object.entries(additionalValues).map(([fname, value]) => [
                    `default_${fname}`,
                    value,
                ])
            )
        );
    }

    /**
     * @param {Object} activity - Activity
     * @param {string} stepType - Activity Type
     * @param {Object} additionalValues
     * @param {string} [afterFakeStepType]
     **/
    async addStepBefore(activity, stepType, additionalValues = {}, afterFakeStepType) {
        if (stepType === "branching") {
            if (afterFakeStepType === "delay") {
                const position = this.getActivityDelayPosition(activity);
                this.coordinates.activityDelayBranches[activity.id] = {
                    x: position.x,
                    y: position.y + 125,
                };
            } else if (afterFakeStepType === "trigger") {
                const position = this.getActivityTriggerPosition(activity);
                this.coordinates.activityTriggerBranches[activity.id] = {
                    x: position.x,
                    y: position.y + 125,
                };
            } else {
                let current = this.getParentMarketingActivity(activity);
                while (current) {
                    if (this.hasActivityNode(current)) {
                        const position = this.getActivityPosition(current);
                        this.coordinates.activityBranches[current.id] = {
                            x: position.x,
                            y: position.y + 125,
                        };
                        return;
                    }
                    if (this.hasDelayNode(current)) {
                        const position = this.getActivityDelayPosition(current);
                        this.coordinates.activityDelayBranches[current.id] = {
                            x: position.x,
                            y: position.y + 125,
                        };
                        return;
                    }
                    if (this.hasTriggerNode(current)) {
                        const position = this.getActivityTriggerPosition(current);
                        this.coordinates.activityTriggerBranches[current.id] = {
                            x: position.x,
                            y: position.y + 125,
                        };
                        return;
                    }
                    const parent = this.getParentMarketingActivity(current);
                    if (!parent) {
                        break;
                    }
                    current = parent;
                }
                if (activity.data.trigger_type === "collect_reply") {
                    const position = this.getReplyTriggerPosition(this.props.record);
                    this.coordinates.replyTriggerBranches[this.props.record.id] = {
                        x: position.x,
                        y: position.y + 125,
                    };
                    return;
                }
                const position = this.getTriggerPosition(this.props.record);
                this.coordinates.triggerBranches[this.props.record.id] = {
                    x: position.x,
                    y: position.y + 125,
                };
            }
            return;
        }
        await this.openFormViewToCreateStep(stepType, async (record) => {
            if (!(await record.checkValidity({ displayNotification: true }))) {
                return false;
            }
            if (!this.props.record.resId || this.props.record.isDirty) {
                await this.props.record.save();
            }
            const values = await this.extractMarketingActivityValues(stepType, record);
            const [res] = await this.orm.call("marketing.campaign", "add_step_before", [
                this.props.record.resId,
                stepType,
                { ...values, ...additionalValues },
                activity.resId,
                afterFakeStepType,
            ]);
            await this.refresh();
            return res;
        });
    }

    /**
     * @param {Record} activity
     * @param {string} afterFakeStepType
     * @param {string} stepType
     * @param {Object} additionalValues
     */
    async addForkingStep(activity, afterFakeStepType, stepType, additionalValues) {
        await this.openFormViewToCreateStep(stepType, async (record) => {
            if (!this.props.record.resId || this.props.record.isDirty) {
                await this.props.record.save();
            }
            const values = await this.extractMarketingActivityValues(stepType, record);
            const [resId] = await this.orm.call("marketing.campaign", "add_forking_step", [
                this.props.record.resId,
                stepType,
                { ...values, ...additionalValues },
                activity?.resId,
                afterFakeStepType,
            ]);
            await this.refresh();
            return resId;
        });
    }

    /**
     * @param {String} stepType
     * @param {Record} record
     * @returns values
     */
    async extractMarketingActivityValues(stepType, record) {
        if (["create_activity", "update_record"].includes(stepType)) {
            await record.save({ reload: false });
            return {
                activity_type: "action",
                server_action_id: record.resId,
                campaign_id: this.props.record.resId,
            };
        }
        return record._getChanges();
    }

    async refresh(record = this.props.record) {
        for (const key of Object.keys(this.coordinates)) {
            this.coordinates[key] = {};
        }
        if (!this.scope.isDestroyed()) {
            await this.props.record.model.load({ resId: record.resId });
        }
    }

    openCampaignTemplatePickerDialog() {
        this.dialog.add(CampaignTemplatePickerDialog, {});
    }

    /**
     * Sorts the step nodes in the plan
     */
    async sortSteps() {
        const record = this.props.record;
        if (!record.resId || record.isDirty) {
            await record.save();
        }
        await this.orm.call("marketing.campaign", "action_sort_steps", [this.props.record.resId]);
        await this.refresh();
    }

    // Pointer Listeners

    /**
     * @param {Record} activity - Activity
     * @param {Event} e1
     */
    addPointerListenerOnMarketingActivity(activity, e1) {
        e1.stopPropagation();
        /** @param {Event} e2 */
        const onMarketingActivityClick = async (e2) => {
            await this.openFormViewToEditStep(activity.data.activity_type, activity.resId);
        };
        /** @param {Event} e2 */
        const onMarketingActivityMove = (e2) => {
            e2.stopPropagation();
            const cursor = this.getCursorPositionOnScreen(e2);
            const position = this.untransform(cursor.x, cursor.y);
            this.coordinates.activities[activity.id] = {
                x: position.x,
                y: position.y,
            };
        };
        /** @param {Event} e2 */
        const onMarketingActivityDrop = async (e2) => {
            e2.stopPropagation();
            const cursor = this.getCursorPositionOnScreen(e2);
            const position = this.untransform(cursor.x, cursor.y);
            const coordinates = activity.data.view_coordinates || {};
            coordinates.activity = {
                x: position.x,
                y: position.y,
            };
            await activity.update({ view_coordinates: coordinates });
            delete this.coordinates.activities[activity.id];
        };
        this.addPointerListeners(
            e1,
            onMarketingActivityClick,
            onMarketingActivityMove,
            onMarketingActivityDrop
        );
    }

    /**
     * @param {Record} activity - Marketing Activity
     * @param {Event} e1
     */
    addPointerListenerOnMarketingActivityDelay(activity, e1) {
        e1.stopPropagation();
        /** @param {Event} e2 */
        const onActivityDelayClick = async (e2) => {
            await this.openFormViewToEditStep("delay", activity.resId);
        };
        /** @param {Event} e2 */
        const onActivityDelayMove = (e2) => {
            e2.stopPropagation();
            const cursor = this.getCursorPositionOnScreen(e2);
            const position = this.untransform(cursor.x, cursor.y);
            this.coordinates.activityDelays[activity.id] = {
                x: position.x,
                y: position.y,
            };
        };
        /** @param {Event} e2 */
        const onActivityDelayDrop = async (e2) => {
            e2.stopPropagation();
            const cursor = this.getCursorPositionOnScreen(e2);
            const position = this.untransform(cursor.x, cursor.y);
            const coordinates = activity.data.view_coordinates || {};
            coordinates.delay = {
                x: position.x,
                y: position.y,
            };
            await activity.update({ view_coordinates: coordinates });
            delete this.coordinates.activityDelays[activity.id];
        };
        this.addPointerListeners(
            e1,
            onActivityDelayClick,
            onActivityDelayMove,
            onActivityDelayDrop
        );
    }

    /**
     * @param {Record} activity
     * @param {Event} e1
     */
    addPointerListenerOnMarketingActivityTrigger(activity, e1) {
        e1.stopPropagation();
        /** @param {Event} e2 */
        const onActivityTriggerClick = async (e2) => {
            await this.openFormViewToEditStep("trigger", activity.resId);
        };
        /** @param {Event} e2 */
        const onActivityTriggerMove = (e2) => {
            e2.stopPropagation();
            const cursor = this.getCursorPositionOnScreen(e2);
            const position = this.untransform(cursor.x, cursor.y);
            this.coordinates.activityTriggers[activity.id] = {
                x: position.x,
                y: position.y,
            };
        };
        /** @param {Event} e2 */
        const onActivityTriggerDrop = async (e2) => {
            e2.stopPropagation();
            const cursor = this.getCursorPositionOnScreen(e2);
            const position = this.untransform(cursor.x, cursor.y);
            const coordinates = activity.data.view_coordinates || {};
            coordinates.trigger = {
                x: position.x,
                y: position.y,
            };
            await activity.update({ view_coordinates: coordinates });
            delete this.coordinates.activityTriggers[activity.id];
        };
        this.addPointerListeners(
            e1,
            onActivityTriggerClick,
            onActivityTriggerMove,
            onActivityTriggerDrop
        );
    }

    /**
     * @param {Record} activity
     * @param {Event} e1
     */
    addPointerListenerOnMarketingActivityFlag(activity, e1) {
        e1.stopPropagation();
        /** @param {Event} e2 */
        const onActivityFlagClick = async (e2) => {};
        /** @param {Event} e2 */
        const onActivityFlagMove = (e2) => {
            e2.stopPropagation();
            const cursor = this.getCursorPositionOnScreen(e2);
            const position = this.untransform(cursor.x, cursor.y);
            this.coordinates.activityFlags[activity.id] = {
                x: position.x,
                y: position.y,
            };
        };
        /** @param {Event} e2 */
        const onActivityFlagDrop = async (e2) => {
            e2.stopPropagation();
            const cursor = this.getCursorPositionOnScreen(e2);
            const position = this.untransform(cursor.x, cursor.y);
            const coordinates = activity.data.view_coordinates || {};
            coordinates.flag = {
                x: position.x,
                y: position.y,
            };
            await activity.update({ view_coordinates: coordinates });
            delete this.coordinates.activityFlags[activity.id];
        };
        this.addPointerListeners(e1, onActivityFlagClick, onActivityFlagMove, onActivityFlagDrop);
    }

    /**
     * @param {Record} campaign
     * @param {Event} e1
     */
    addPointerListenerOnReplyTrigger(campaign, e1) {
        e1.stopPropagation();
        /** @param {Event} e2 */
        const onReplyTriggerClick = async (e2) => {
            const action = "marketing_automation.marketing_campaign_create_reply_trigger";
            await this.action.doAction(action, {
                props: { resId: this.props.record.resId },
            });
        };
        /** @param {Event} e2 */
        const onReplyTriggerMove = (e2) => {
            e2.stopPropagation();
            const cursor = this.getCursorPositionOnScreen(e2);
            const position = this.untransform(cursor.x, cursor.y);
            this.coordinates.replyTriggers[campaign.id] = {
                x: position.x,
                y: position.y,
            };
        };
        /** @param {Event} e2 */
        const onReplyTriggerDrop = async (e2) => {
            e2.stopPropagation();
            const cursor = this.getCursorPositionOnScreen(e2);
            const position = this.untransform(cursor.x, cursor.y);
            const coordinates = campaign.data.view_coordinates || {};
            coordinates.reply_trigger = {
                x: position.x,
                y: position.y,
            };
            await campaign.update({ view_coordinates: coordinates });
            delete this.coordinates.replyTriggers[campaign.id];
        };
        this.addPointerListeners(e1, onReplyTriggerClick, onReplyTriggerMove, onReplyTriggerDrop);
    }

    /**
     * @param {Record} campaign
     * @param {Event} e1
     */
    addPointerListenerOnTrigger(campaign, e1) {
        e1.stopPropagation();
        /** @param {Event} e2 */
        const onTriggerClick = async (e2) => {
            const action = "marketing_automation.marketing_campaign_create_trigger";
            await this.action.doAction(action, {
                props: { resId: this.props.record.resId },
                onClose: ({ noReload } = {}) => {
                    if (!noReload) {
                        return this.props.record.load();
                    }
                },
            });
        };
        /** @param {Event} e2 */
        const onTriggerMove = (e2) => {
            e2.stopPropagation();
            const cursor = this.getCursorPositionOnScreen(e2);
            const position = this.untransform(cursor.x, cursor.y);
            this.coordinates.triggers[campaign.id] = {
                x: position.x,
                y: position.y,
            };
        };
        /** @param {Event} e2 */
        const onTriggerDrop = async (e2) => {
            e2.stopPropagation();
            const cursor = this.getCursorPositionOnScreen(e2);
            const position = this.untransform(cursor.x, cursor.y);
            const coordinates = campaign.data.view_coordinates || {};
            coordinates.trigger = {
                x: position.x,
                y: position.y,
            };
            await campaign.update({ view_coordinates: coordinates });
            delete this.coordinates.triggers[campaign.id];
        };
        this.addPointerListeners(e1, onTriggerClick, onTriggerMove, onTriggerDrop);
    }

    /**
     * @param {Record} activity
     * @param {Event} e1
     */
    addPointerListenerOnTriggerFlag(campaign, e1) {
        e1.stopPropagation();
        /** @param {Event} e2 */
        const onTriggerFlagClick = (e2) => {};
        /** @param {Event} e2 */
        const onTriggerFlagMove = (e2) => {
            e2.stopPropagation();
            const cursor = this.getCursorPositionOnScreen(e2);
            const position = this.untransform(cursor.x, cursor.y);
            this.coordinates.triggerFlags[campaign.id] = {
                x: position.x,
                y: position.y,
            };
        };
        /** @param {Event} e2 */
        const onTriggerFlagDrop = async (e2) => {
            e2.stopPropagation();
            const cursor = this.getCursorPositionOnScreen(e2);
            const position = this.untransform(cursor.x, cursor.y);
            const coordinates = campaign.data.view_coordinates || {};
            coordinates.trigger_flag = {
                x: position.x,
                y: position.y,
            };
            await campaign.update({ view_coordinates: coordinates });
            delete this.coordinates.triggerFlags[campaign.id];
        };
        this.addPointerListeners(e1, onTriggerFlagClick, onTriggerFlagMove, onTriggerFlagDrop);
    }

    /**
     * @param {Record} activity
     * @param {Event} e1
     * @param {string} fakeStepType
     */
    addPointerListenerOnActivityBranchFlag(activity, fakeStepType, e1) {
        e1.stopPropagation();
        /** @param {Event} e2 */
        const onActivityBranchClick = (e2) => {
            if (fakeStepType === "delay") {
                delete this.coordinates.activityDelayBranches[activity.id];
            } else if (fakeStepType === "trigger") {
                delete this.coordinates.activityTriggerBranches[activity.id];
            } else {
                delete this.coordinates.activityBranches[activity.id];
            }
        };
        /** @param {Event} e2 */
        const onActivityBranchMove = (e2) => {
            e2.stopPropagation();
            const cursor = this.getCursorPositionOnScreen(e2);
            const position = this.untransform(cursor.x, cursor.y);
            if (fakeStepType === "delay") {
                this.coordinates.activityDelayBranches[activity.id] = {
                    x: position.x,
                    y: position.y,
                };
            } else if (fakeStepType === "trigger") {
                this.coordinates.activityTriggerBranches[activity.id] = {
                    x: position.x,
                    y: position.y,
                };
            } else {
                this.coordinates.activityBranches[activity.id] = {
                    x: position.x,
                    y: position.y,
                };
            }
        };
        /** @param {Event} e2 */
        const onActivityBranchDrop = async (e2) => {
            e2.stopPropagation();
        };
        this.addPointerListeners(
            e1,
            onActivityBranchClick,
            onActivityBranchMove,
            onActivityBranchDrop
        );
    }

    /**
     * @param {Record} campaign
     * @param {string} additionalValues
     * @param {Event} e1
     */
    addPointerListenerOnCampaignBranchFlag(campaign, additionalValues, e1) {
        e1.stopPropagation();
        /** @param {Event} e2 */
        const onCampaignBranchClick = (e2) => {
            if (additionalValues.trigger_type === "collect_reply") {
                delete this.coordinates.replyTriggerBranches[campaign.id];
            } else {
                delete this.coordinates.triggerBranches[campaign.id];
            }
        };
        /** @param {Event} e2 */
        const onCampaignBranchMove = (e2) => {
            e2.stopPropagation();
            const cursor = this.getCursorPositionOnScreen(e2);
            const position = this.untransform(cursor.x, cursor.y);
            if (additionalValues.trigger_type === "collect_reply") {
                this.coordinates.replyTriggerBranches[campaign.id] = {
                    x: position.x,
                    y: position.y,
                };
            } else {
                this.coordinates.triggerBranches[campaign.id] = {
                    x: position.x,
                    y: position.y,
                };
            }
        };
        /** @param {Event} e2 */
        const onCampaignBranchDrop = (e2) => {
            e2.stopPropagation();
        };
        this.addPointerListeners(
            e1,
            onCampaignBranchClick,
            onCampaignBranchMove,
            onCampaignBranchDrop
        );
    }

    /**
     * @param {Record} activity
     * @param {Event} e1
     */
    addPointerListenerOnBranchNoFlag(activity, e1) {
        e1.stopPropagation();
        /** @param {Event} e2 */
        const onNoBranchClick = (e2) => {};
        /** @param {Event} e2 */
        const onNoBranchMove = (e2) => {
            e2.stopPropagation();
            const cursor = this.getCursorPositionOnScreen(e2);
            const position = this.untransform(cursor.x, cursor.y);
            this.coordinates.noBranches[activity.id] = {
                x: position.x,
                y: position.y,
            };
        };
        /** @param {Event} e2 */
        const onNoBranchDrop = async (e2) => {
            e2.stopPropagation();
            const cursor = this.getCursorPositionOnScreen(e2);
            const position = this.untransform(cursor.x, cursor.y);
            const coordinates = activity.data.view_coordinates || {};
            coordinates.no_branch_flag = {
                x: position.x,
                y: position.y,
            };
            await activity.update({ view_coordinates: coordinates });
            delete this.coordinates.noBranches[activity.id];
        };
        this.addPointerListeners(e1, onNoBranchClick, onNoBranchMove, onNoBranchDrop);
    }

    /**
     * @param {Record} activity
     * @param {Event} e1
     */
    addPointerListenerOnBranchYesFlag(activity, e1) {
        e1.stopPropagation();
        /** @param {Event} e2 */
        const onYesBranchClick = (e2) => {};
        /** @param {Event} e2 */
        const onYesBranchMove = (e2) => {
            e2.stopPropagation();
            const cursor = this.getCursorPositionOnScreen(e2);
            const position = this.untransform(cursor.x, cursor.y);
            this.coordinates.yesBranches[activity.id] = {
                x: position.x,
                y: position.y,
            };
        };
        /** @param {Event} e2 */
        const onYesBranchDrop = async (e2) => {
            e2.stopPropagation();
            const cursor = this.getCursorPositionOnScreen(e2);
            const position = this.untransform(cursor.x, cursor.y);
            const coordinates = activity.data.view_coordinates || {};
            coordinates.yes_branch_flag = {
                x: position.x,
                y: position.y,
            };
            await activity.update({ view_coordinates: coordinates });
            delete this.coordinates.yesBranches[activity.id];
        };
        this.addPointerListeners(e1, onYesBranchClick, onYesBranchMove, onYesBranchDrop);
    }

    /**
     * @param {Event} event
     * @returns {{ x: double, y: double }}
     */
    getCursorPositionOnScreen(event) {
        const container = event.target.closest(".editor");
        const bounds = container.getBoundingClientRect();
        return {
            x: event.clientX - bounds.left,
            y: event.clientY - bounds.top,
        };
    }

    /** @returns {boolean} */
    hasVisibleNode(activity) {
        return (
            this.hasTriggerNode(activity) ||
            this.hasDelayNode(activity) ||
            this.hasActivityNode(activity)
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
    getPositionOfLastVisibleNode(activity) {
        let current = activity;
        while (current) {
            if (this.hasActivityNode(current)) {
                return this.getActivityPosition(current);
            }
            if (this.hasDelayNode(current)) {
                return this.getActivityDelayPosition(current);
            }
            if (this.hasTriggerNode(current)) {
                return this.getActivityTriggerPosition(current);
            }
            const parent = this.getParentMarketingActivity(current);
            if (!parent) {
                if (current.data.trigger_type === "collect_reply") {
                    return this.getReplyTriggerPosition(this.props.record);
                } else {
                    return this.getTriggerPosition(this.props.record);
                }
            }
            current = parent;
        }
        return this.getTriggerPosition(this.props.record);
    }

    /**
     * @param {Record} activity
     * @returns {{ x: double, y: double }}
     */
    getPositionOfLastVisibleNodeOnScreen(activity) {
        const position = this.getPositionOfLastVisibleNode(activity);
        return this.transform(position.x, position.y);
    }

    /**
     * @param {Record} campaign
     * @returns {{ x: double, y: double }}
     */
    getTriggerPosition(campaign) {
        return (
            this.coordinates.triggers[campaign.id] ?? {
                x: campaign.data.view_coordinates?.trigger?.x || 0,
                y: campaign.data.view_coordinates?.trigger?.y || 0,
            }
        );
    }

    /**
     * Returns the position of the trigger node on screen.
     * @param {Record} campaign
     * @returns {{ x: double, y: double }}
     */
    getTriggerPositionOnScreen(campaign) {
        const position = this.getTriggerPosition(campaign);
        return this.transform(position.x, position.y);
    }

    /**
     * Returns the position of the campaign trigger flag on screen.
     * @param {Record} campaign
     * @returns {{ x: double, y: double }}
     */
    getTriggerFlagPositionOnScreen(campaign) {
        const position = this.coordinates.triggerFlags[campaign.id] ?? {
            x: campaign.data.view_coordinates?.trigger_flag?.x || 0,
            y: campaign.data.view_coordinates?.trigger_flag?.y || 0,
        };
        return this.transform(position.x, position.y);
    }

    /**
     * @param {Record} campaign
     * @returns {{ x: double, y: double }}
     */
    getReplyTriggerPosition(campaign) {
        return (
            this.coordinates.replyTriggers[campaign.id] ?? {
                x: campaign.data.view_coordinates?.reply_trigger?.x || 0,
                y: campaign.data.view_coordinates?.reply_trigger?.y || 0,
            }
        );
    }

    /**
     * @param {Record} campaign
     * @returns {{ x: double, y: double }}
     */
    getReplyTriggerPositionOnScreen(campaign) {
        const position = this.getReplyTriggerPosition(campaign);
        return this.transform(position.x, position.y);
    }

    /**
     * @param {Record} activity - Marketing Activity
     * @returns {{ x: double, y: double }}
     */
    getActivityPosition(activity) {
        return (
            this.coordinates.activities[activity.id] ?? {
                x: activity.data.view_coordinates?.activity?.x || 0,
                y: activity.data.view_coordinates?.activity?.y || 0,
            }
        );
    }

    /**
     * Returns the position of the marketing activity on screen.
     * @param {Record} activity - Marketing Activity
     * @returns {{ x: double, y: double }}
     */
    getActivityPositionOnScreen(activity) {
        const position = this.getActivityPosition(activity);
        return this.transform(position.x, position.y);
    }

    /**
     * Returns the position of the flag on screen.
     * @param {Record} activity - Marketing Activity
     * @returns {{ x: double, y: double }}
     */
    getActivityFlagPositionOnScreen(activity) {
        const position = this.coordinates.activityFlags[activity.id] ?? {
            x: activity.data.view_coordinates?.flag?.x || 0,
            y: activity.data.view_coordinates?.flag?.y || 0,
        };
        return this.transform(position.x, position.y);
    }

    /**
     * @param {Record} activity - Marketing Activity
     * @returns {{ x: double, y: double }}
     */
    getActivityTriggerPosition(activity) {
        return (
            this.coordinates.activityTriggers[activity.id] ?? {
                x: activity.data.view_coordinates?.trigger?.x || 0,
                y: activity.data.view_coordinates?.trigger?.y || 0,
            }
        );
    }

    /**
     * Returns the position of the activity trigger on screen.
     * @param {Record} activity - Marketing Activity
     * @returns {{ x: double, y: double }}
     */
    getActivityTriggerPositionOnScreen(activity) {
        const position = this.getActivityTriggerPosition(activity);
        return this.transform(position.x, position.y);
    }

    /**
     * @param {Record} activity - Marketing Activity
     * @returns {{ x: double, y: double }}
     */
    getActivityDelayPosition(activity) {
        return (
            this.coordinates.activityDelays[activity.id] ?? {
                x: activity.data.view_coordinates?.delay?.x || 0,
                y: activity.data.view_coordinates?.delay?.y || 0,
            }
        );
    }

    /**
     * Returns the position of the marketing activity on screen.
     * @param {Record} activity - Marketing Activity
     * @returns {{ x: double, y: double }}
     */
    getActivityDelayPositionOnScreen(activity) {
        const position = this.getActivityDelayPosition(activity);
        return this.transform(position.x, position.y);
    }

    /**
     * @param {Record} activity - Marketing Activity
     * @returns {{ x: double, y: double }}
     */
    getBranchFlagPositionOnScreen(activity) {
        const position = this.coordinates.branches[activity.id] ?? { x: 0, y: 0 };
        return this.transform(position.x, position.y);
    }

    /**
     * @param {Record} activity - Marketing Activity
     * @returns {{ x: double, y: double }}
     */
    getYesBranchPositionOnScreen(activity) {
        const position = this.coordinates.yesBranches[activity.id] ?? {
            x: activity.data.view_coordinates?.yes_branch_flag?.x || 0,
            y: activity.data.view_coordinates?.yes_branch_flag?.y || 0,
        };
        return this.transform(position.x, position.y);
    }

    /**
     * @param {Record} activity - Marketing Activity
     * @returns {{ x: double, y: double }}
     */
    getNoBranchPositionOnScreen(activity) {
        const position = this.coordinates.noBranches[activity.id] ?? {
            x: activity.data.view_coordinates?.no_branch_flag?.x || 0,
            y: activity.data.view_coordinates?.no_branch_flag?.y || 0,
        };
        return this.transform(position.x, position.y);
    }
}

export const campaignFlowView = {
    ...x2ManyField,
    component: CampaignFlowView,
    additionalClasses: ["d-flex", "flex-column", "flex-grow-1", "flex-md-row", "flex-basis-0", "m-0"],
    fieldDependencies: [
        { name: "model_id", type: "many2one" },
        { name: "enroll_type", type: "selection" },
        { name: "enroll_action_type", type: "selection" },
    ],
};

registry.category("fields").add("campaign_flow_view", campaignFlowView);
