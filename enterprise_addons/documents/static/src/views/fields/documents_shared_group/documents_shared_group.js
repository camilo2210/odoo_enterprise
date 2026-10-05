import { Component, useProps } from "@odoo/owl";
import { DocumentsGroupAvatar } from "./documents_group_avatar";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class DocumentsSharedGroupField extends Component {
    static template = "documents.DocumentsSharedGroupField";
    props = useProps(standardFieldProps);
    static components = {
        DocumentsGroupAvatar,
    };

    get userIds() {
        const users = this.props.record.data[this.props.name]["user_ids"] || [];
        return users.map((user) => user.id);
    }

    get userCount() {
        return this.userIds.length;
    }
}

export const documentsSharedGroupField = {
    component: DocumentsSharedGroupField,
    relatedFields: [
        {
            name: "user_ids",
            type: "many2many",
            relation: "res.users",
        },
    ],
};

registry.category("fields").add("documents_shared_group", documentsSharedGroupField);
