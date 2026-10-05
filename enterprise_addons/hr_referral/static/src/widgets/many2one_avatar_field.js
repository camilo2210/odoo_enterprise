import { Avatar } from "@mail/views/web/fields/avatar/avatar";
import { Component, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { computeM2OProps, KanbanMany2One } from "@web/views/fields/many2one/many2one";
import {
    buildM2OFieldDescription,
    many2OneFieldProps,
} from "@web/views/fields/many2one/many2one_field";

export class ReferralCardMany2OneAvatarUserField extends Component {
    static template = "hr_referral.ReferralCardMany2OneAvatarUserField";
    static components = { Avatar, KanbanMany2One };
    props = useProps({ ...many2OneFieldProps });

    get m2oProps() {
        return {
            ...computeM2OProps(this.props),
            readonly: false,
        };
    }
}

registry.category("fields").add("card.referral_many2one_avatar_user", {
    ...buildM2OFieldDescription(ReferralCardMany2OneAvatarUserField),
    additionalClasses: ["o_field_many2one_avatar"],
});
