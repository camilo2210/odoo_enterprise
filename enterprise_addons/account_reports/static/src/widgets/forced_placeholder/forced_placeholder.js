import { Component, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { computeM2OProps, Many2One, many2OneProps } from "@web/views/fields/many2one/many2one";
import { buildM2OFieldDescription, many2OneFieldProps } from "@web/views/fields/many2one/many2one_field";

export class ForcedPlaceholder extends Many2One {
    static template = "account_reports.ForcedPlaceholder";
    props = useProps({ ...many2OneProps });
}

export class ForcedPlaceholderField extends Component {
    static template = "account_reports.ForcedPlaceholderField";
    static components = { ForcedPlaceholder };
    props = useProps(many2OneFieldProps);

    get m2oProps() {
        const props = computeM2OProps(this.props);
        return {
            ...props,
            canOpen: !props.readonly && props.canOpen, // no link nor hand cursor on an empty readonly field
        };
    }
}

registry.category("fields").add("account_reports.forced_placeholder", {
    ...buildM2OFieldDescription(ForcedPlaceholderField),
});
