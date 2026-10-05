import { proxy } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";


export class AttendanceManagementListController extends ListController {
    static template = "hr_attendance.AttendanceManagementListView";
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.state = proxy({});
    }

    async onSelectionChanged() {
        await super.onSelectionChanged();
        let selection;
        if ((selection = await this.model.root.getResIds(true))){
            this.state.selected_states = await this.orm.read("hr.attendance", selection, ["l10n_sa_late_hours_status"]);
        }
    }

    displayButton(button) {
        const displayHeaderButtons = {
            action_approve_l10n_sa_late_hours: true,
            action_refuse_l10n_sa_late_hours: true,
        };
        for (const record of this.state.selected_states) {
            if (record.l10n_sa_late_hours_status !== "to_approve") displayHeaderButtons.action_approve_l10n_sa_late_hours = false;
            if (record.l10n_sa_late_hours_status !== "approved") displayHeaderButtons.action_refuse_l10n_sa_late_hours = false;

            // Early exit if all already false
            if (Object.values(displayHeaderButtons).every(value => !value))
                break;
        }
        return displayHeaderButtons[button.clickParams.name] ?? true;
    }
}

export const attendanceManagementListView = {
    ...listView,
    Controller: AttendanceManagementListController,
};

registry.category("views").add("hr_attendance_management_list", attendanceManagementListView);
