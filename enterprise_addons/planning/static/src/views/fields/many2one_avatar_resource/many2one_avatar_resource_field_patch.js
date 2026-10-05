import { AvatarCard } from "@mail/core/web/avatar_card/avatar_card";
import {
    cardMany2OneAvatarResourceField,
    CardMany2OneAvatarResourceField,
} from "@resource_mail/views/fields/many2one_avatar_resource/kanban_many2one_avatar_resource_field";
import {
    Many2OneAvatarResourceField,
    many2OneAvatarResourceField,
} from "@resource_mail/views/fields/many2one_avatar_resource/many2one_avatar_resource_field";
import { usePopover } from "@web/core/popover/popover_hook";
import { patch } from "@web/core/utils/patch";

function patchFieldComponent(o) {
    patch(o, {
        setup() {
            super.setup();
            this.materialPopover = usePopover(AvatarCard);
        },
        openMaterialPopover(target) {
            if (
                !this.materialPopover.isOpen &&
                this.props.record.data.resource_roles?.currentIds.length <= 1
            ) {
                return;
            }
            this.materialPopover.open(target, {
                id: this.props.record.data[this.props.name].id,
                model: this.props.record.fields[this.props.name].relation,
            });
        },
    });
}

patchFieldComponent(Many2OneAvatarResourceField.prototype);
patchFieldComponent(CardMany2OneAvatarResourceField.prototype);

function patchFieldDescr(o) {
    patch(o, {
        fieldDependencies: [
            ...o.fieldDependencies,
            {
                name: "resource_roles",
                type: "many2many",
            },
            {
                name: "resource_color",
                type: "integer",
            },
        ],
    });
}

patchFieldDescr(many2OneAvatarResourceField);
patchFieldDescr(cardMany2OneAvatarResourceField);
