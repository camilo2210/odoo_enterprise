import { patch } from "@web/core/utils/patch";
import { SendReceiptPopup } from "@point_of_sale/app/components/popups/send_receipt_popup/send_receipt_popup";

patch(SendReceiptPopup.prototype, {
    showPhoneInput() {
        return super.showPhoneInput() || this.pos.config.whatsapp_enabled;
    },
    actionSendReceiptOnWhatsapp() {
        this.sendReceipt.call({
            action: "action_sent_receipt_on_whatsapp",
            destination: this.state.phone,
            name: "WhatsApp",
        });
    },
    get sendList() {
        const list = super.sendList;
        if (this.pos.config.whatsapp_enabled) {
            list.find((item) => item.model === "phone").buttons.push({
                click: () => this.actionSendReceiptOnWhatsapp(),
                status:
                    this.sendReceipt.lastArgs?.[0]?.name == "WhatsApp" && this.sendReceipt.status,
                icon: "oi_whatsapp",
                iconClass: "oi-lg",
                disabled: () => !this.isValidPhone,
            });
        }
        return list;
    },
});
