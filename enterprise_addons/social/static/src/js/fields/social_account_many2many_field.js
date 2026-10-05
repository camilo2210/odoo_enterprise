import { registry } from "@web/core/registry";
import {
    Many2ManyCheckboxesField,
    many2ManyCheckboxesField,
} from "@web/views/fields/many2many_checkboxes/many2many_checkboxes_field";

export class SocialAccountMany2manyField extends Many2ManyCheckboxesField {
    static template = "social.SocialAccountMany2manyField";

    get webNameSearchSpecification() {
        return {
            ...super.webNameSearchSpecification,
            name: {},
            media_id: { fields: { id: {}, name: {} } },
        };
    }
}

export const socialAccountMany2manyField = {
    ...many2ManyCheckboxesField,
    component: SocialAccountMany2manyField,
};

registry.category("fields").add("social_account_many2many_field", socialAccountMany2manyField);
