import { AvatarCard } from "@mail/core/web/avatar_card/avatar_card";
import { avatarProps } from "@mail/views/web/fields/avatar/avatar";
import { GanttEmployeeAvatar } from "@hr_gantt/hr_gantt_employee_avatar";
import { usePopover } from "@web/core/popover/popover_hook";
import { ORM } from "@web/core/orm_plugin";
import { usePlugin, t, useProps, signal, onWillStart } from "@odoo/owl";
import { useBus, useService } from "@web/core/utils/hooks";
import { useDateTimePicker } from "@web/core/datetime/datetime_picker_hook";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";

export class HrHolidaysGanttAvatarCard extends AvatarCard {
    static template = "hr_holidays_gantt.AvatarCard";

    setup() {
        super.setup(...arguments);
        this.props = useProps({
            close: t.function([]),
            id: t.number(),
            model: t.selection(AvatarCard.allowedModels),
            scale: t.string().optional(),
        });
        this.orm = usePlugin(ORM);
        this.action = useService("action");
        this.datetimePickerTargetRef = signal.ref();

        this.dateTimePicker = useDateTimePicker({
            target: this.datetimePickerTargetRef,
            onApply: (date) => {
                if (date) {
                    this.createVersion(date);
                }
            },
            get pickerProps() {
                return { type: "date" };
            },
        });

        onWillStart(async () => {
            this.canCreateEmployeeRecord = await user.hasGroup("hr.group_hr_user");
        });
    }

    async createVersion(date) {
        const version_id = await this.orm.call("hr.employee", "create_version", [
            this.employee?.id,
            { date_version: date },
        ]);
        if (version_id) {
            this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "hr.employee",
                res_id: this.employee?.id,
                views: [[false, "form"]],
                target: "current",
                context: {
                    version_id: version_id,
                },
            });
        }
    }

    onClickDateTimePickerBtn() {
        this.dateTimePicker.open();
    }

    get leaveSummary() {
        return this.employee?.avatar_leave_summary || [];
    }

    get workingScheduleLabel() {
        const hours = this.employee?.avatar_hours_per_week;
        return hours ? _t("%s h / Week", hours) : _t("Time Off");
    }

    get dashboardScale() {
        const scale = this.props.scale;
        return !scale || scale === "quarter" ? "year" : scale;
    }

    async onTimeOffClick() {
        const employeeId = this.employee?.id;
        if (!employeeId) {
            return;
        }
        const action = await this.orm.call(
            "hr.employee",
            "action_time_off_dashboard",
            [[employeeId]],
            { scale: this.dashboardScale }
        );
        if (action) {
            await this.actionService.doAction(action);
        }
    }

    get hasFooter() {
        return false;
    }
}

export class HrHolidaysGanttEmployeeAvatar extends GanttEmployeeAvatar {
    props = useProps({ ...avatarProps, scale: t.string().optional() });

    static template = "hr.HrHolidaysGanttEmployeeAvatar";

    imageRef = signal.ref();

    setup() {
        super.setup(...arguments);
        this.avatarCard = usePopover(HrHolidaysGanttAvatarCard);

        useBus(
            this.env.bus,
            "HR_GANTT:OPEN_AVATAR_CARD",
            ({ detail: { resId, resModel } } = {}) => {
                if (
                    resId !== this.props.resId ||
                    resModel !== this.props.resModel ||
                    this.avatarCard.isOpen
                ) {
                    return;
                }
                const target = this.imageRef();
                if (target) {
                    this.openCard({ currentTarget: target });
                }
            }
        );
    }

    openCard(ev) {
        if (this.uiService.isSmall || !this.props.resId) {
            return;
        }
        const target = ev.currentTarget;
        if (!this.avatarCard.isOpen) {
            this.avatarCard.open(target, {
                id: this.props.resId,
                model: this.props.resModel,
                scale: this.props.scale,
            });
        }
    }
}
