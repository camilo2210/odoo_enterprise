import { registry } from "@web/core/registry";
import {
    Many2ManyTagsAvatarUserField,
    many2ManyTagsAvatarUserField,
} from "@mail/views/web/fields/many2many_avatar_user_field/many2many_avatar_user_field";

/**
 * Hide the members if we already show them in the responsible list.
 */
export class Many2manyTagsResGroupUsers extends Many2ManyTagsAvatarUserField {
    get tags() {
        const responsibles = this.props.record.data.responsible_ids.records;
        const responsibleIds = responsibles.map((r) => r._config.resId);
        const records = this.props.record.data[this.props.name].records;
        const resIdToId = Object.fromEntries(records.map((r) => [r.id, r._config.resId]));
        return super.tags.filter((r) => !responsibleIds.includes(resIdToId[r.id]));
    }
}

registry.category("fields").add("many2many_tags_res_group_users", {
    ...many2ManyTagsAvatarUserField,
    fieldDependencies: [
        { name: "responsible_ids", type: "many2many" },
        ...(many2ManyTagsAvatarUserField.fieldDependencies || []),
    ],
    component: Many2manyTagsResGroupUsers,
});
