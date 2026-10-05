import { t, useProps } from "@odoo/owl";
import { TimesheetMany2OneAvatarEmployeeGridRow } from "@timesheet_grid/components/timesheet_many2one_avatar_employee_grid_row/timesheet_many2one_avatar_employee_grid_row";
import { patch } from "@web/core/utils/patch";

patch(TimesheetMany2OneAvatarEmployeeGridRow.prototype, {
    setup() {
        super.setup();

        this.saleTimesheetProps = useProps({
            targetLimitsSet: t.boolean().optional(false),
        });
    },
    get timesheetOvertimeProps() {
        const { month } = this.employeeOvertimeProps();
        return {
            ...super.timesheetOvertimeProps,
            month,
            targetLimitsSet: this.saleTimesheetProps.targetLimitsSet,
        };
    },
});
