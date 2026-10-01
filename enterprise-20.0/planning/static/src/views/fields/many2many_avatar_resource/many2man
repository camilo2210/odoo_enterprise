import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";
import {
    cardMany2ManyAvatarResourceField,
    CardMany2ManyAvatarResourceField,
    listMany2ManyAvatarResourceField,
    ListMany2ManyAvatarResourceField,
    Many2ManyAvatarResourceField,
    many2ManyAvatarResourceField,
    Many2ManyTagsAvatarResourceFieldPopover,
} from "@resource_mail/views/fields/many2many_avatar_resource/many2many_avatar_resource_field";

patch(Many2ManyAvatarResourceField.prototype, {
    displayAvatarCard(record) {
        return (
            !this.uiService.isSmall &&
            this.relation === "resource.resource" &&
            (record.data.resource_type === "user" || record.data.role_ids.currentIds.length > 1)
        );
    },
});

const oldRelatedFields = many2ManyAvatarResourceField.relatedFields;
many2ManyAvatarResourceField.relatedFields = (fieldInfo) => [
    ...oldRelatedFields(fieldInfo),
    {
        name: "role_ids",
        type: "many2many",
    },
];

const WithAutoAddAssignedMaterialsMixin = (T) =>
    class AutoAddAssignedMaterialsMixin extends T {
        setup() {
            super.setup(...arguments);
            const superUpdate = this.update;
            this.update = async (resources) => {
                const resourcesOnShift = new Set(
                    this.props.record.data[this.props.name].records.map((r) => r.resId)
                );
                const addedResources = resources
                    .map((r) => r.id)
                    .filter((id) => !resourcesOnShift.has(id));
                if (!addedResources.length) {
                    return superUpdate(resources);
                }
                const assignedMaterials = await this.orm.call(
                    "resource.resource",
                    "get_materials_assigned_to_human_resources",
                    [addedResources]
                );
                const materialsToAdd = assignedMaterials
                    .map((id) => ({ id }))
                    .filter((id) => !resourcesOnShift.has(id) && !resources.includes(id));
                return superUpdate([...resources, ...materialsToAdd]);
            };
        }
    };

export class PlanningMany2ManyAvatarResourceField extends WithAutoAddAssignedMaterialsMixin(
    Many2ManyAvatarResourceField
) {}
export const planningMany2ManyAvatarResourceField = {
    ...many2ManyAvatarResourceField,
    component: PlanningMany2ManyAvatarResourceField,
};

export class PlanningListMany2ManyAvatarResourceField extends WithAutoAddAssignedMaterialsMixin(
    ListMany2ManyAvatarResourceField
) {}
export const planningListMany2ManyAvatarResourceField = {
    ...listMany2ManyAvatarResourceField,
    component: PlanningListMany2ManyAvatarResourceField,
};

export class PlanningMany2ManyTagsAvatarResourceFieldPopover extends WithAutoAddAssignedMaterialsMixin(
    Many2ManyTagsAvatarResourceFieldPopover
) {}

export class PlanningCardMany2ManyAvatarResourceField extends WithAutoAddAssignedMaterialsMixin(
    CardMany2ManyAvatarResourceField
) {
    static PopoverClass = PlanningMany2ManyTagsAvatarResourceFieldPopover;
}
export const planningCardMany2ManyAvatarResourceField = {
    ...cardMany2ManyAvatarResourceField,
    component: PlanningCardMany2ManyAvatarResourceField,
};

registry
    .category("fields")
    .add("planning_many2many_avatar_resource", planningMany2ManyAvatarResourceField);

registry
    .category("fields")
    .add("list.planning_many2many_avatar_resource", planningListMany2ManyAvatarResourceField);

registry
    .category("fields")
    .add("card.planning_many2many_avatar_resource", planningCardMany2ManyAvatarResourceField);
