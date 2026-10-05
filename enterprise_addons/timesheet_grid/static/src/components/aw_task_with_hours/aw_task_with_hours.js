import { registry } from "@web/core/registry";
import { TaskWithHours } from "@hr_timesheet/components/task_with_hours/task_with_hours";
import { buildM2OFieldDescription } from "@web/views/fields/many2one/many2one_field";


export class AwTaskWithHours extends TaskWithHours {
    get m2oProps() {
        const props = super.m2oProps;
        return {
            ...props,
            onRecordSaved: async (record) => {
                await props.onRecordSaved(record);
                await this.env.onLinkedTaskRecordSaved?.();
            },
        };
    }
}

registry.category("fields").add("aw_task_with_hours", {
    ...buildM2OFieldDescription(AwTaskWithHours),
});
