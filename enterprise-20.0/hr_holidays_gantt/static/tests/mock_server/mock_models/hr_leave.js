import { fields } from "@web/../tests/web_test_helpers";
import { HrLeave } from "@hr_holidays/../tests/mock_server/mock_models/hr_leave";

export class HrHolidaysGanttLeave extends HrLeave {
    _views = {
        ...super._views,
        gantt: `
            <gantt js_class="hr_holidays_gantt_manager_hr_leave"
                   date_start="date_from"
                   date_stop="date_to"
                   multi_create_view="multi_create_form"
                   default_group_by="employee_id">
                <field name="state" invisible="1"/>
                <field name="work_entry_type_id" invisible="1"/>
            </gantt>
        `,
        form: `<form><field name="name"/></form>`,
    };

    name = fields.Char();
    employee_id = fields.Many2one({ relation: "hr.employee", required: true });
    can_approve = fields.Boolean();
    can_validate = fields.Boolean();
    can_refuse = fields.Boolean();
    can_back_to_approve = fields.Boolean();
    work_entry_type_id = fields.Many2one({ relation: "hr.work.entry.type" });
}
