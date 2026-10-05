import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import {
    Many2OneResourceCalendarField,
    many2OneResourceCalendarField,
} from "@resource/views/fields/resource_calendar_many2one/resource_calendar_many2one";

export class WorkingScheduleField extends Many2OneResourceCalendarField {
	setup() {
		super.setup();
	    this.orm = useService("orm");
	    this.action = useService("action");
	}

	async _onWorkingScheduleUpdate(currentValue, originalUpdate) {
		const action = await this.orm.call(
			"hr.version",
			"action_employee_work_schedule_change_wizard",
			[this.props.record.data.version_id.id, currentValue.id],
		);

	    if (!action) {
			await originalUpdate(currentValue);
			return;
	    }

		this.action.doAction(action);
	}

	get m2oProps() {
        const p = super.m2oProps;
        const value = p.value && { ...p.value };
        return {
            ...p,
            update: (value) => {
				if (!value || !this.props.record.resId) {
                    return p.update(value);
                }
                return this._onWorkingScheduleUpdate(value, p.update);
            },
            value,
        };
    }
}

export const workingScheduleField = {
    ...many2OneResourceCalendarField,
    component: WorkingScheduleField,
};

registry.category("fields").add("working_schedule_field", workingScheduleField);
