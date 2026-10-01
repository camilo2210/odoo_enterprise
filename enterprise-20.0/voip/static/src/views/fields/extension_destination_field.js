import { Avatar } from "@mail/views/web/fields/avatar/avatar";
import { status } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { referenceField, ReferenceField } from "@web/views/fields/reference/reference_field";

const DESTINATION_INFO = {
    "voip.call.flow": { icon: "account_tree", label: _t("Call Flow") },
    "voip.extension": { icon: "phone", icon_class: "oi-filled", label: _t("Extension") },
    "voip.call.group": { icon: "group", icon_class: "oi-filled", label: _t("Group") },
    "voip.ivr": { icon: "format_list_numbered", label: _t("Menu") },
    "voip.queue": { icon: "headphones", label: _t("Queue") },
    "voip.sound": { icon: "volume_up", label: _t("Sound") },
    "res.users": { label: _t("User") },
    "res.partner": { label: _t("Contact") },
    "voip.voicemail": { icon: "inbox", label: _t("Voice Mailbox") },
};

export class ExtensionDestinationField extends ReferenceField {
    static template = "voip.ExtensionDestinationField";
    static components = {
        ...ReferenceField.components,
        Avatar,
    };

    get destination() {
        return this.getValue();
    }

    get destinationInfo() {
        return DESTINATION_INFO[this.getRelation()] || {};
    }

    get hasDestinationAvatar() {
        return ["res.users", "res.partner"].includes(this.getRelation());
    }

    get m2oProps() {
        const props = super.m2oProps;
        if (props.relation === "voip.call.flow") {
            return {
                ...props,
                canCreate: false,
                canCreateEdit: false,
                canQuickCreate: false,
            };
        }
        if (props.relation !== "res.users") {
            return props;
        }
        return {
            ...props,
            canCreate: false,
            canCreateEdit: false,
            canQuickCreate: false,
            domain: () => [...props.domain(), ["share", "=", false]],
        };
    }

    async updateModel(relation) {
        this.state.currentRelation = relation;
        await this.props.record.update({ [this.props.name]: false });
        if (!relation || this.getRelation() !== relation) {
            return;
        }
        const { context, domain } = this.m2oProps;
        const [destination] = await this.props.record.model.orm.searchRead(
            relation,
            domain(),
            ["display_name"],
            { context, limit: 1 }
        );
        if (status(this) === "destroyed" || this.getRelation() !== relation) {
            return;
        }
        if (destination) {
            await this.updateM2O(destination);
        } else {
            await this.props.record.setInvalidField(this.props.name);
        }
    }

    async updateM2O(value) {
        const resModel = this.state.currentRelation || this.getRelation();
        await this.props.record.update({
            [this.props.name]: value && {
                resModel,
                resId: value.id,
                displayName: value.display_name,
            },
        });
        if (!value && resModel) {
            await this.props.record.setInvalidField(this.props.name);
        }
    }
}

registry.category("fields").add("voip_extension_destination", {
    ...referenceField,
    component: ExtensionDestinationField,
    displayName: _t("Extension Destination"),
});
