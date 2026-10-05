import { registry } from "@web/core/registry";
import { buildM2OFieldDescription, Many2OneField } from "@web/views/fields/many2one/many2one_field";

export class WorksheetTemplateMany2One extends Many2OneField {
    get m2oProps() {
        const props = super.m2oProps;
        return {
            ...props,
            update: async (value) => {
                await props.update(value);
                await this.props.record.save();
            },
        };
    }
}

registry.category("fields").add("worksheet_template_many2one", {
    ...buildM2OFieldDescription(WorksheetTemplateMany2One),
});
