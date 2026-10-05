import { TimesheetSystray, TimesheetSystrayContent } from "@timesheet_grid/components/timesheet_systray_menu/timesheet_systray";
import { patch } from "@web/core/utils/patch";
import { onWillStart, t, useProps } from "@odoo/owl";

patch(TimesheetSystrayContent.prototype, {
    setup() {
        super.setup();
        this.hrAttendanceProps = useProps({
            signInOut: t.function().optional(),
            attendanceCheckInPermission: t.boolean().optional(),
        });
    },
});

patch(TimesheetSystray.prototype, {
    setup() {
        super.setup(...arguments);
        onWillStart(async () => {
            this.lazySession.getValue("attendance_check_in_ability", (hasAbility) => {
                this.state.isDisplayed &&= !hasAbility;
            });
        });
    }
});
