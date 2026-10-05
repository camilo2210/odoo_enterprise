import { omit } from "@web/core/utils/objects";
import { Many2OneField, many2OneFieldProps } from "@web/views/fields/many2one/many2one_field";

import { Component, toRaw, useProps } from "@odoo/owl";

export class DocumentsDetailsMany2OneField extends Component {
    static components = { Many2OneField };
    props = useProps({
        ...many2OneFieldProps,
        readonlyPlaceholder: many2OneFieldProps.placeholder,
    });
    static template = "documents.DocumentsDetailsMany2One";

    get value() {
        return toRaw(this.props.record.data[this.props.name]);
    }

    get fieldProps() {
        return omit(this.props, "readonlyPlaceholder");
    }
}
