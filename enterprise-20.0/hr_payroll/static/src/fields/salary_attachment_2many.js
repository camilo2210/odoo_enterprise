import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class SalaryAttachment2ManyField extends X2ManyField {
    /**
     * @override
     */
    setup() {
        super.setup();
        this.orm = useService("orm");
    }

    async onDelete(record) {
        await this.orm.call("hr.salary.attachment", "action_close", [record.resId], {
            context: this.props.context,
        });
        await this.orm.call("hr.salary.attachment", "unlink", [record.resId], {
            context: this.props.context,
        });
        this.props.record.load();
    }

    get rendererProps() {
        const props = super.rendererProps;
        if (this.props.viewMode === "kanban") {
            return props;
        }
        props.activeActions.onDelete = this.onDelete.bind(this);
        return props;
    }
}

export const salaryAttachment2ManyField = {
    ...x2ManyField,
    component: SalaryAttachment2ManyField,
};

registry.category("fields").add("salary_attachment_2many", salaryAttachment2ManyField);
