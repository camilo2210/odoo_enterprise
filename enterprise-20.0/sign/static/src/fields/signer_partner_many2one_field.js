/** @odoo-module **/

import { Many2OneField } from "@web/views/fields/many2one/many2one_field";
import { usePopover } from "@web/core/popover/popover_hook";
import { useService } from "@web/core/utils/hooks";
import { RecipientsInputTagsListPopover } from "@mail/core/web/recipients_input_tags_list_popover";
import { _t } from "@web/core/l10n/translation";
import { useEffect } from "@odoo/owl";

export class SignerPartnerMany2One extends Many2OneField {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.emailSetterPopover = usePopover(RecipientsInputTagsListPopover, {
            closeOnClickAway: false,
            position: "bottom-start",
        });
        const extractPartnerId = (value) => Array.isArray(value) ? value[0] : value?.id;
        let initialized = false;
        useEffect(() => {
            const currentId = extractPartnerId(this.props.record.data[this.props.name]);
            if (initialized && currentId) {
                this.checkEmailAndOpenPopover(currentId);
            }
            initialized = true;
        });
    }

    async checkEmailAndOpenPopover(partnerId) {
        const [partner] = await this.orm.read("res.partner", [partnerId], ["email", "name"]);
        
        if (!partner.email) {
            const targetEl = document.activeElement || document.body;
            
            this.emailSetterPopover.open(targetEl, {
                tagToUpdate: {
                    name: partner.name,
                    onDelete: () => {
                        this.props.record.update({ [this.props.name]: false });
                    }
                },
                onUpdateTag: async (newEmail) => {
                    await this.orm.write("res.partner", [partnerId], { email: newEmail });
                    this.notification.add(_t("Email saved successfully!"), { type: "success" });
                }
            });
        }
    }
}
