import { markup } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { CalendarCommonRenderer } from "@web/views/calendar/calendar_common/calendar_common_renderer";
import { PlanningCalendarCommonPopover } from "@planning/views/planning_calendar/common/planning_calendar_common_popover";

const { DateTime } = luxon;

export class PlanningCalendarCommonRenderer extends CalendarCommonRenderer {
    static components = {
        ...CalendarCommonRenderer.components,
        Popover: PlanningCalendarCommonPopover,
    };

    setup() {
        super.setup();
        this.notificationService = useService("notification");
    }

    /**
     * @override
     */
    eventClassNames(info) {
        const classesToAdd = super.eventClassNames(info);
        const { event } = info;
        const model = this.props.model;
        const record = model.records[event.id];

        if (record && model.highlightIds && !model.highlightIds.includes(record.id)) {
            classesToAdd.push("opacity-25");
        }
        return classesToAdd;
    }

    /**
     * @override
     */
    async onEventScheduled(info) {
        const original = info.event;
        const date = DateTime.fromJSDate(original.start);
        const resId = Number(original.id);
        const result = await this.props.model.scheduleEvent(resId, date);
        original.remove();

        if (!result.slots_assigned_ids.length) {
            this.notificationService.add(_t("Resources unavailable for the selected period."), {
                type: "danger",
            });
            return;
        }

        const notifLabel =
            result.schedule_type === "full"
                ? _t("Shift scheduled")
                : _t("Shift partially scheduled");

        this.closeNotificationFn?.();
        this.closeNotificationFn = this.notificationService.add(
            markup`<i class="fa fa-fw fa-check"></i><span class="ms-1">${notifLabel}</span>`,
            {
                type: "success",
                className: "planning_notification",
                buttons: [
                    {
                        name: _t("Undo"),
                        icon: "undo",
                        onClick: async () => {
                            this.closeNotificationFn?.();
                            try {
                                await this.props.model.orm.call(
                                    this.props.model.meta.resModel,
                                    "undo_assign_slot",
                                    [
                                        [resId],
                                        result.undo_data.slots_created_ids,
                                        result.undo_data.undo_vals,
                                    ]
                                );
                                this.props.model.load();
                                this.closeNotificationFn = this.notificationService.add(
                                    markup`<i class="fa fa-fw fa-check"></i><span class="ms-1">${_t(
                                        "Shift unscheduled"
                                    )}</span>`,
                                    {
                                        type: "success",
                                        className: "planning_notification",
                                    }
                                );
                            } catch {
                                this.closeNotificationFn = this.notificationService.add(
                                    markup`<i class="fa fa-fw fa-times"></i><span class="ms-1">${_t(
                                        "Could not undo scheduling"
                                    )}</span>`,
                                    {
                                        type: "danger",
                                        className: "planning_notification",
                                    }
                                );
                            }
                        },
                    },
                ],
            }
        );
    }
}
