import { Component, useProps, t } from "@odoo/owl";

import { url } from "@web/core/utils/urls";
import { DiscussAvatar } from "@mail/core/common/discuss_avatar";

/**
 * Displays general information (avatar, name, etc.) about the contact
 * associated with the given call.
 */
export class ContactInfo extends Component {
    static components = { DiscussAvatar };
    props = useProps({
        contact: t.or([t.object(), t.boolean(), t.literal(null)]).optional(null),
        phoneNumber: t.string().optional(),
        alias: t.string().optional(),
        extraClass: t.string().optional(""),
    });
    static template = "voip.ContactInfo";

    /** @returns {?string} */
    get avatarUrl() {
        if (!this.contact) {
            return null;
        }
        return url("/web/image", {
            model: "res.partner",
            id: this.contact.id,
            field: "avatar_128",
        });
    }

    /** @returns {import("models").ResPartner} */
    get contact() {
        return this.props.contact;
    }

    /** @returns {string} */
    get contactInfo() {
        if (!this.contact) {
            return ""; // TODO
        }
        const info = [];
        if (this.contact.parent_name) {
            info.push(this.contact.parent_name);
        }
        // ⚠ French: function = job position
        if (this.contact.function) {
            info.push(this.contact.function);
        }
        return info.join(", ");
    }

    /** @returns {string} */
    get contactName() {
        return this.props.alias || this.contact?.voipName || this.props.phoneNumber;
    }
}
