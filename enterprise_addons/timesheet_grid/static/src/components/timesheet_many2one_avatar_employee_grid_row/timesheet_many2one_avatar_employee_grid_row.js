import { AvatarCard } from "@mail/core/web/avatar_card/avatar_card";
import { Component, computed, onWillStart, useProps } from "@odoo/owl";
import { usePopover } from "@web/core/popover/popover_hook";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { omit } from "@web/core/utils/objects";
import { gridRowProps } from "@web_grid/components/grid_row/grid_row";
import {
    Many2OneGridRow,
    many2OneGridRow,
    many2OneGridRowProps,
} from "@web_grid/components/many2one_grid_row/many2one_grid_row";
import { useTimesheetOvertimeProps } from "../../hooks/useTimesheetOvertimeProps";
import { EmployeeOvertimeIndication } from "../employee_overtime_indication/employee_overtime_indication";

export class TimesheetMany2OneAvatarEmployeeGridRow extends Component {
    static template = "timesheet_grid.TimesheetMany2OneAvatarEmployeeGridRow";
    static components = {
        Many2OneGridRow,
        EmployeeOvertimeIndication,
    };

    props = useProps({
        ...gridRowProps,
        ...many2OneGridRowProps,
    });

    many2OneProps = computed(() => omit(this.props, "classNames"));

    resId = computed(() => this.value && this.value[0]);

    setup() {
        this.employeeOvertimeProps = useTimesheetOvertimeProps(this.resId);
        this.avatarCard = usePopover(AvatarCard);
        this.uiService = useService("ui");

        /* Before the component starts, check if the current user belongs to the HR user group.
        This information is used to determine the appropriate relation for the component.*/
        onWillStart(async () => {
            this.isHrUser = await user.hasGroup("hr.group_hr_user");
        });
    }

    // Chooses employee data visibility based on user role.
    get relation() {
        return this.isHrUser
            ? this.props.model.fieldsInfo[this.props.name].relation
            : "hr.employee.public";
    }

    get displayName() {
        return this.value ? this.value[1] : "";
    }

    get value() {
        return this.props.value ?? this.props.row.initialRecordValues[this.props.name];
    }

    get timesheetOvertimeProps() {
        const { units_to_work, uom, worked_hours } = this.employeeOvertimeProps();
        return {
            allocated_hours: units_to_work,
            uom,
            worked_hours,
        };
    }

    openCard(ev) {
        if (this.uiService.isSmall) {
            return;
        }
        const target = ev.currentTarget;
        if (!this.avatarCard.isOpen) {
            this.avatarCard.open(target, {
                id: this.resId(),
                model: this.relation,
            });
        }
    }
}

export const timesheetMany2OneAvatarEmployeeGridRow = {
    ...many2OneGridRow,
    component: TimesheetMany2OneAvatarEmployeeGridRow,
};

registry
    .category("grid_components")
    .add("timesheet_many2one_avatar_employee", timesheetMany2OneAvatarEmployeeGridRow);
