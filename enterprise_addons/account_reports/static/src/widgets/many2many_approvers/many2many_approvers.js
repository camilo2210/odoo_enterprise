import { registry } from "@web/core/registry";
import {
    CardMany2ManyTagsAvatarUserField,
    cardMany2ManyTagsAvatarUserField,
} from "@mail/views/web/fields/many2many_avatar_user_field/many2many_avatar_user_field";
import { _t } from "@web/core/l10n/translation";


export class Many2ManyAvatarUserApprover extends CardMany2ManyTagsAvatarUserField {
    get assignBtnTooltip() {
        return _t("Approve");
    }
}

export const many2ManyAvatarUserApprover = {
    ...cardMany2ManyTagsAvatarUserField,
    component: Many2ManyAvatarUserApprover,
};

registry.category("fields").add("many2many_avatar_user_approver", many2ManyAvatarUserApprover);
