import { registry } from "@web/core/registry";
import { Component, useProps } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { TagsList } from "@web/core/tags_list/tags_list";
import { BadgeTag } from "@web/core/tags_list/badge_tag";

export class JsonTagsField extends Component {
    static template = "obox.JsonTagsField";
    static components = { TagsList, BadgeTag };

    props = useProps(standardFieldProps);

    get tags() {
        const values = this.props.record.data[this.props.name];
        return Array.isArray(values) ? values.map((text) => ({ text })) : [];
    }
}

registry.category("fields").add("json_tags", { component: JsonTagsField });
