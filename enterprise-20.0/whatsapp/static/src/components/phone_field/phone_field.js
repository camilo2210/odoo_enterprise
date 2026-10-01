import { t } from "@odoo/owl";

import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { PhoneField, phoneField, phoneFieldProps } from "@web/views/fields/phone/phone_field";

phoneFieldProps.enableWhatsAppButton = t.boolean().optional(true);

patch(PhoneField.prototype, {
    setup() {
        super.setup();
        this.action = useService("action");
    },
    get actionButtons() {
        if (!this.props.enableWhatsAppButton || !this.value) {
            return super.actionButtons;
        }
        return [
            ...super.actionButtons,
            {
                icon: "oi_whatsapp",
                onSelected: async () => {
                    await this.props.record.save();
                    this.action.doAction(
                        {
                            type: "ir.actions.act_window",
                            target: "new",
                            name: _t("Send WhatsApp Message"),
                            res_model: "whatsapp.composer",
                            views: [[false, "form"]],
                            context: {
                                ...user.context,
                                active_model: this.props.record.resModel,
                                active_id: this.props.record.resId,
                                default_phone: this.dialNumber,
                            },
                        },
                        {
                            onClose: () => {
                                this.props.record.load();
                                this.props.record.model.notify();
                            },
                        }
                    );
                },
                name: _t("WhatsApp"),
            },
        ];
    },
});

const patchDescr = {
    extractProps({ options }) {
        const props = super.extractProps(...arguments);
        props.enableWhatsAppButton = options.enable_whatsapp;
        return props;
    },
    supportedOptions: [
        ...(phoneField.supportedOptions ? phoneField.supportedOptions : []),
        {
            label: _t("Enable WhatsApp"),
            name: "enable_whatsapp",
            type: "boolean",
            default: true,
        },
    ],
};

patch(phoneField, patchDescr);
