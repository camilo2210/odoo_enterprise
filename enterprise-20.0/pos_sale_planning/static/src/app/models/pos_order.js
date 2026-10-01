import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(PosOrder.prototype, {
    get hasResourcePayment() {
        return this.payment_ids.some((payment) => payment.payment_method_id.type === "resource");
    },
    // @Override
    addPaymentline(payment_method, args = {}) {
        this.assertEditable();
        if (
            payment_method.type === "resource" &&
            this.lines.some((line) => line.sale_order_origin_id)
        ) {
            return {
                status: false,
                data: _t(
                    "You cannot add a resource linked payment method when the order contains lines coming from a sale order. You can split the order if you want to pay the other lines with this payment method."
                ),
            };
        }
        const result = super.addPaymentline(...arguments);
        if (result.status && payment_method.type === "resource") {
            if (args.planning_slot_id) {
                this.setSlot(args.planning_slot_id);
            }
            this.setToInvoice(false);
        }
        return result;
    },
    setToInvoice(to_invoice) {
        super.setToInvoice(...arguments);
        if (to_invoice && this.hasResourcePayment) {
            this.to_invoice = false;
        }
    },
    setPartner(partner) {
        const resourceLinkedPayment = this.payment_ids.find(
            (paymentline) => paymentline.payment_method_id.type === "resource"
        );
        if (
            resourceLinkedPayment &&
            partner !== resourceLinkedPayment.planning_slot_id.partner_id
        ) {
            return;
        }
        super.setPartner(...arguments);
    },
    setSlot(planning_slot_id) {
        this.planning_slot_id = planning_slot_id;
    },
});
