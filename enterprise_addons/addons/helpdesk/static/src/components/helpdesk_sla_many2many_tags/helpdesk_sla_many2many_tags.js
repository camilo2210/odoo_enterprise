import { Component, useProps, t } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { BadgeTag, badgeTagProps } from "@web/core/tags_list/badge_tag";
import {
    Many2ManyTagsField,
    many2ManyTagsField,
} from "@web/views/fields/many2many_tags/many2many_tags_field";

class SLATag extends Component {
    static template = "helpdesk.SLATag";
    static components = { BadgeTag };
    props = useProps({
        ...badgeTagProps,
        slaStatus: t.string(),
    });

    get SLAStatusIcon() {
        if (this.props.slaStatus === "failed") {
            return "cancel";
        } else if (this.props.slaStatus === "reached") {
            return "check_circle";
        }
        return "";
    }
}

class HelpdeskSLAMany2ManyTags extends Many2ManyTagsField {
    static components = { ...Many2ManyTagsField.components, Tag: SLATag };
    getTagProps(record) {
        return { ...super.getTagProps(record), slaStatus: record.data.status };
    }
}

export const helpdeskSLAMany2ManyTags = {
    ...many2ManyTagsField,
    component: HelpdeskSLAMany2ManyTags,
    relatedFields: (fieldInfo) => [
        ...many2ManyTagsField.relatedFields(fieldInfo),
        { name: "status", type: "selection", selection: [] },
    ],
    additionalClasses: [...(many2ManyTagsField.additionalClasses || []), "o_field_many2many_tags"],
};

registry.category("fields").add("helpdesk_sla_many2many_tags", helpdeskSLAMany2ManyTags);
