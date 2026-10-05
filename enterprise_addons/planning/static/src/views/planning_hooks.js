import { useEnv } from "@web/owl2/utils";
import { _t } from "@web/core/l10n/translation";
import { markup, onWillUnmount, proxy, useEffect } from "@odoo/owl";
import { serializeDateTime } from "@web/core/l10n/dates";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog, deleteConfirmationMessage } from "@web/core/confirmation_dialog/confirmation_dialog";
import { AddressRecurrencyConfirmationDialog } from "@planning/components/address_recurrency_confirmation_dialog/address_recurrency_confirmation_dialog";

/**
 * @param {Object} params
 * @param {() => any} params.getAdditionalContext
 * @param {() => any} params.getDomain
 * @param {() => any} params.getRecords
 * @param {() => any} params.getResModel
 * @param {() => luxon.DateTime} params.getStartDate
 * @param {() => any} params.toggleHighlightPlannedFilter
 * @param {() => Promise<any>} params.reload
 */
export class PlanningControllerActions {
    constructor({
        getAdditionalContext,
        getDomain,
        getRecords,
        getResModel,
        getStartDate,
        getStopDate,
        toggleHighlightPlannedFilter,
        reload,
    }) {
        this.getAdditionalContext = getAdditionalContext;
        this.getDomain = getDomain;
        this.getRecords = getRecords;
        this.getResModel = getResModel;
        this.getStartDate = getStartDate;
        this.getStopDate = getStopDate;
        this.toggleHighlightPlannedFilter = toggleHighlightPlannedFilter;
        this.reload = reload;
        this.actionService = useService("action");
        this.env = useEnv();
        this.notifications = useService("notification");
        this.orm = useService("orm");
    }

    async copyPrevious() {
        const resModel = this.getResModel();
        const startDate = serializeDateTime(this.getStartDate());
        const domain = this.getDomain();
        const result = await this.orm.call(resModel, "action_copy_previous_week", [
            startDate,
            domain,
        ]);
        if (result) {
            const notificationRemove = this.notifications.add(
                markup`<i class="oi oi-fw" data-icon="check"></i><span class="ms-1">${_t(
                    "Previous week's shifts copied"
                )}</span>`,
                {
                    type: "success",
                    sticky: true,
                    className: "planning_notification",
                    buttons: [{
                        name: 'Undo',
                        icon: 'undo',
                        onClick: async () => {
                            await this.orm.call(
                                resModel,
                                'action_rollback_copy_previous_week',
                                result,
                            );
                            this.toggleHighlightPlannedFilter(false);
                            this.notifications.add(
                                markup`<i class="oi oi-fw" data-icon="check"></i><span class="ms-1">${_t(
                                    "Previous week's copied shifts removed"
                                )}</span>`,
                                { type: 'success' },
                            );
                            notificationRemove();
                        },
                    }],
                }
            );
            this.toggleHighlightPlannedFilter(result[0]);

            this.notificationFn = notificationRemove;

        } else {
            this.notifications.add(
                _t(
                    "There are no shifts planned for the previous week, or they have already been copied."
                ),
                { type: "danger" }
            );
        }
    }

    async publish() {
        const records = this.getRecords();
        if (!records?.length) {
            return this.notifications.add(
                _t(
                    "The shifts have already been published, or there are no shifts to publish."
                ),
                { type: "danger" }
            );
        }
        const additionalContext = this.getAdditionalContext();
        const adjustedEndDate = this.getStopDate();
        if (adjustedEndDate) {
            additionalContext.default_end_datetime = serializeDateTime(adjustedEndDate.endOf('day'));
        }
        return this.actionService.doAction("planning.planning_send_action", {
            additionalContext,
            onClose: this.reload,
        });
    }

    async autoPlan(callback = async () => {}) {
        const additionalContext = this.getAdditionalContext();
        const res = await this.orm.call(
            this.getResModel(),
            "auto_plan_ids",
            [this.autoPlanDomain()],
            {
                context: {
                    ...additionalContext,
                    add_materials_assigned_to_employees: true,
                },
            }
        );
        const { open_shift_assigned = [], sale_line_planned = [] } = res;
        if (!open_shift_assigned.length && !sale_line_planned.length) {
            this.notifications.add(this.autoPlanFailureNotification(), { type: "danger" });
            return res;
        }
        await callback(res);

        let multipleClickProtection = false;
        const notificationRemove = this.notifications.add(
            markup`<i class="oi oi-fw" data-icon="check"></i><span class="ms-1">${this.autoPlanSuccessNotification()}</span>`,
            {
                type: "success",
                sticky: true,
                buttons: [
                    {
                        name: "Undo",
                        icon: "undo",
                        onClick: async () => {
                            if (multipleClickProtection) {
                                return;
                            }
                            multipleClickProtection = true;
                            await this.orm.call(
                                this.getResModel(),
                                "action_rollback_auto_plan_ids",
                                [res]
                            );
                            await this.reload();
                            this.notifications.add(
                                markup`<i class="oi oi-fw" data-icon="check"></i><span class="ms-1">${this.autoPlanRollbackSuccessNotification()
                                    }</span>`,
                                { type: "success" }
                            );
                            this.toggleHighlightPlannedFilter(false);
                            notificationRemove();
                        },
                    },
                ],
            }
        );
        this.toggleHighlightPlannedFilter([...open_shift_assigned, ...sale_line_planned]);
        this.notificationFn = notificationRemove;
        return res;
    }

    async print(groupBy = null) {
        const resModel = this.getResModel();
        const startDate = serializeDateTime(this.getStartDate());
        const stopDate = serializeDateTime(this.getStopDate());
        const domain = this.getDomain();
        const result = await this.orm.call(resModel, "action_print_plannings", [
            startDate,
            stopDate,
            groupBy,
            domain,
        ]);
        if (result) {
            this.actionService.doAction(result);
        } else {
            this.notifications.add(
                _t(
                    "No shifts to print"
                ),
                { type: "warning" }
            );
        }
    }

    autoPlanDomain() {
        return this.getDomain();
    }

    autoPlanSuccessNotification() {
        return _t("Open shifts assigned");
    }

    autoPlanFailureNotification() {
        return _t(
            "All open shifts have already been assigned, or there are no resources available to take them at this time."
        );
    }

    autoPlanRollbackSuccessNotification() {
        return _t("Open shifts unscheduled");
    }
}

export function usePlanningControllerActions() {
    const planningControllerActions = new PlanningControllerActions(...arguments);

    onWillUnmount(() => {
        planningControllerActions.notificationFn?.();
    });

    return planningControllerActions;
}

export function usePlanningModelActions({ getHighlightPlannedIds, getContext }) {
    const orm = useService("orm");
    return {
        async getHighlightIds() {
            const context = getContext();
            if (!context.highlight_needs_attention && !context.highlight_planned) {
                return;
            }
            const highlightedPlannedIds = context.highlight_planned ? getHighlightPlannedIds() : [];
            const needsAttentionIds = context.highlight_needs_attention
                ? await orm.call("planning.slot", "get_needs_attention_slot_ids", [])
                : [];
            return Array.from(new Set([...needsAttentionIds, ...highlightedPlannedIds]));
        },
    };
}

export function setupDisplayName(displayNameRef) {
    useEffect(() => {
        if (!displayNameRef()) {
            return;
        }
        const displayNameMatch = displayNameRef().textContent.match(/^(.*)(\(.*\))$/);
        if (displayNameMatch) {
            const textMuted = document.createElement("span");
            textMuted.className = "text-muted text-truncate";
            textMuted.textContent = displayNameMatch[2];
            const displayNameText = document.createElement("span");
            displayNameText.textContent = displayNameMatch[1];
            displayNameRef().replaceChildren(displayNameText);
            displayNameRef().appendChild(textMuted);
        } else {
            displayNameRef().replaceChildren(document.createTextNode(displayNameRef().textContent));
        }
    });
}

export function usePlanningRecurringDeleteAction() {
    const orm = useService("orm");
    return {
        async _actionAddressRecurrency(shift, recurrenceUpdate) {
            if (['subsequent', 'all'].includes(recurrenceUpdate)) {
                await orm.call(
                    shift.resModel,
                    'action_address_recurrency',
                    [shift.resId, recurrenceUpdate],
                );
            }
        },
        _setRecurrenceUpdate(recurrenceUpdate) {
            this.state.recurrenceUpdate = recurrenceUpdate;
        },
    };
}

/**
 * Builds the "Unschedule"/"Delete" popover actions shared by the gantt and
 * map renderers' getPopoverProps: same recurrence-aware delete confirmation,
 * same unschedule call, only the orm/resModel/reload differ per view.
 */
export function usePlanningPopoverActions() {
    const dialogService = useService("dialog");
    const state = proxy({ recurrenceUpdate: "this" });
    const planningRecurrenceDeletion = usePlanningRecurringDeleteAction();

    return {
        makeOnUnschedule({ orm, resModel, record, reload }) {
            if (["1_draft", "2_published"].includes(record.state) && record.start_datetime) {
                return async () => {
                    await orm.call(resModel, "action_unschedule", [record.id]);
                    await reload();
                };
            }
            return;
        },
        makeOnDelete({ orm, resModel, record, reload }) {
            return async () => {
                const recurrenceProps = { resId: record.id, resModel };
                const canProceed = await new Promise((resolve) => {
                    if (record.repeat) {
                        dialogService.add(AddressRecurrencyConfirmationDialog, {
                            cancel: () => resolve(false),
                            close: () => resolve(false),
                            confirm: async () => {
                                await planningRecurrenceDeletion._actionAddressRecurrency(
                                    recurrenceProps,
                                    state.recurrenceUpdate
                                );
                                resolve(true);
                            },
                            onChangeRecurrenceUpdate: (value) => {
                                state.recurrenceUpdate = value;
                            },
                            selected: state.recurrenceUpdate,
                        });
                    } else {
                        dialogService.add(ConfirmationDialog, {
                            title: _t("Bye-bye, record!"),
                            body: deleteConfirmationMessage,
                            confirmLabel: _t("Delete"),
                            cancel: () => resolve(false),
                            close: () => resolve(false),
                            confirm: () => resolve(true),
                        });
                    }
                });
                if (canProceed) {
                    await orm.unlink(resModel, [record.id]);
                    await reload();
                }
            };
        },
    };
}
