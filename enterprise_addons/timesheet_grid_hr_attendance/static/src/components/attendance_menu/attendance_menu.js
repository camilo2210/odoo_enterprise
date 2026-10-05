import { onWillStart, proxy } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { ActivityMenu } from "@hr_attendance/components/attendance_menu/attendance_menu";
import { TimesheetSystrayContent } from "@timesheet_grid/components/timesheet_systray_menu/timesheet_systray";
import { useCommand } from "@web/core/commands/command_hook";
import { _t } from "@web/core/l10n/translation";

patch(ActivityMenu, {
    components: { ...ActivityMenu.components, TimesheetSystrayContent },
});

patch(ActivityMenu.prototype, {
    setup() {
        super.setup(...arguments);
        this.action = useService("action");
        this.menu = useService("menu");
        this.orm = useService("orm");
        this.staticTimerService = useService("static_timesheet_timer");

        Object.assign(
            this.state,
            proxy({
                showAssistant: false,
                showTimesheetsSystray: false,
                activeTab: "timesheets",
            })
        );
        onWillStart(async () => {
            this.lazySession.getValue("display_timesheets_assistant", (value) => {
                this.state.showAssistant = value;
            });
            this.lazySession.getValue("display_timesheets_systray", (value) => {
                this.state.showTimesheetsSystray = value;
            });
        });

        useCommand(
            _t("Open Timesheets Systray"),
            () => {
                this.dropdown.open();
            },
            {
                category: "activity",
                hotkey: "alt+shift+r",
                isAvailable: () => this.state.checkedIn && this.state.showTimesheetsSystray,
            }
        );
    },

    async openSystrayTab(tab) {
        // Reviewing again would fold the attendances back and drop the record being edited.
        if (this.state.activeTab === tab) {
            return;
        }
        this.state.activeTab = tab;
        if (tab === "attendance") {
            await this.openAttendanceReview();
        }
    },

    async beforeDropdownOpen() {
        this.state.activeTab = "timesheets";
        return super.beforeDropdownOpen(...arguments);
    },

    _searchReadEmployeeFill(employee) {
        super._searchReadEmployeeFill(employee);

        if (this.state.showTimesheetsSystray) {
            this.staticTimerService.initTimer().then(() => {
                if (this.state.checkedIn) {
                    this.staticTimerService.resumeTimer();
                } else {
                    this.staticTimerService.pauseTimer();
                }
            });
        }
    },

    get closeSystrayOnCheckIn() {
        return !!this.state.checkedIn;
    },

    async openAssistantAction() {
        // Open the timesheets app first
        const [, menuId] = await this.orm.call("ir.model.data", "check_object_reference", [
            "hr_timesheet",
            "timesheet_menu_root",
        ]);
        if (menuId) {
            this.menu.setCurrentMenu(menuId);
        }

        this.action.doAction({
            type: "ir.actions.client",
            tag: "hr_timesheet_activitywatch_action",
        });
        this.dropdown?.close();
    },
});
