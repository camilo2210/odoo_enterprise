import { patch } from "@web/core/utils/patch";
import { GeneratePrinterData } from "@point_of_sale/app/utils/printer/generate_printer_data";

/**
 * This class is a JS copy of the class PosOrderReceipt in Python.
 */
patch(GeneratePrinterData.prototype, {
    generateReceiptData() {
        const data = super.generateReceiptData(...arguments);
        const identifier = this.order.providerOrderId;

        if (!identifier) {
            return data;
        }

        const deliveryCustomerData = this.order.deliveryCustomerData;
        data.partner = {
            ...data.partner,
            name: deliveryCustomerData.name,
            address: deliveryCustomerData.address,
            phone: deliveryCustomerData.phone,
            email: deliveryCustomerData.email,
        };

        data.conditions.is_urban_piper_order = Boolean(this.order.delivery_identifier);
        data.extra_data.ext_platforms_id = [identifier.slice(0, -4), identifier.slice(-4)];
        data.extra_data.delivery_provider_name = this.order.getDeliveryProviderName();
        data.extra_data.delivery_otp = this.order.deliveryOtp || "";
        data.extra_data.is_instant_order = this.order.isInstantOrder;

        return data;
    },
    generatePreparationData() {
        const data = super.generatePreparationData(...arguments);

        for (const receipt of data) {
            receipt.extra_data.delivery_provider_name = this.order.getDeliveryProviderName();
            receipt.extra_data.delivery_otp = this.order.deliveryOtp || "";
            receipt.extra_data.is_instant_order = this.order.isInstantOrder;
        }

        return data;
    },
});
