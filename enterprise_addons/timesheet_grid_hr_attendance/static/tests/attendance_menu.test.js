import { beforeEach, expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { contains, mountWithCleanup, onRpc } from "@web/../tests/web_test_helpers";
import { ActivityMenu } from "@hr_attendance/components/attendance_menu/attendance_menu";

import { defineTimesheetModels } from "@timesheet_grid/../tests/hr_timesheet_models";
import { setupTimesheetEnvironment } from "@timesheet_grid/../tests/timesheet_timer_helpers";

const env = setupTimesheetEnvironment();

defineTimesheetModels();

const displayedTab = ["show", "active"];

let checkedIn;

function attendanceUserData() {
    return {
        id: 7,
        name: "John Timesheet",
        attendance_state: checkedIn ? "checked_in" : "checked_out",
        last_attendance_worked_hours: 2,
        today_attendance_ids: [
            {
                id: 42,
                check_in: "2026-08-27 09:00:00",
                check_out: checkedIn ? false : "2026-08-27 11:00:00",
                worked_hours: 2,
                can_edit: true,
            },
        ],
    };
}

beforeEach(() => {
    checkedIn = true;
    Object.assign(env.sessionData, {
        attendance_check_in_ability: true,
        attendance_state: "checked_in",
        attendance_break_management: false,
        attendance_capture_check_in: false,
        attendance_device_tracking: false,
    });
    onRpc("/hr_attendance/attendance_user_data", attendanceUserData);
    onRpc("/hr_attendance/systray_check_in_out", () => {
        checkedIn = !checkedIn;
        return attendanceUserData();
    });
});

test("checking in again after an attendance edit checked us out shows a single tab", async () => {
    const attendanceMenu = await mountWithCleanup(ActivityMenu);

    await contains("button:has(i[aria-label='Attendance'])").click();
    expect("#timesheet_recording_tab").toHaveClass(displayedTab);
    expect("#attendance_review_tab").not.toHaveClass("active");

    await contains("#attendance_review_tab_button").click();
    expect("#attendance_review_tab").toHaveClass(displayedTab);
    expect("#timesheet_recording_tab").not.toHaveClass("active");

    checkedIn = false;
    await attendanceMenu.searchReadEmployee();
    await animationFrame();
    expect("[role='tablist']").toHaveCount(0, {
        message: "a checked out employee has no timesheet tab to switch to",
    });
    expect("#attendance_review_tab").toHaveCount(1);

    await contains(".o_wrap_btn_sign_out button:contains(Check in)").click();
    await animationFrame();
    expect("[role='tablist']").toHaveCount(1);
    expect("#attendance_review_tab").toHaveClass(displayedTab);
    expect("#timesheet_recording_tab").not.toHaveClass("active", {
        message: "the tab we left is still the only one displayed",
    });
});
