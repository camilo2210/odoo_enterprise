import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { useService } from "@web/core/utils/hooks";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { PlanningSlotSelectionPopup } from "@pos_sale_planning/app/components/planning_slot_selection_popup/planning_slot_selection_popup";

patch(PaymentScreen.prototype, {
    setup(vals) {
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        return super.setup(...arguments);
    },
    async addNewPaymentLine(paymentMethod, args = {}) {
        if (paymentMethod.type !== "resource") {
            return super.addNewPaymentLine(...arguments);
        }
        if (this.currentOrder.hasResourcePayment) {
            this.notification.add(
                _t(
                    "You cannot add another payment method if there is already a resource-linked payment on the order."
                ),
                {
                    type: "warning",
                }
            );
            return;
        }
        if (this.currentOrder.payment_ids.length > 0) {
            this.notification.add(
                _t(
                    "You cannot pay with a resource-linked payment method if there are already other payments."
                ),
                {
                    type: "warning",
                }
            );
            return;
        }
        const availableSlots = await this.pos.fetchSlots(paymentMethod, this.currentOrder);
        const selectedSlot = await makeAwaitable(this.dialog, PlanningSlotSelectionPopup, {
            paymentMethodId: paymentMethod.id,
            orderUuid: this.currentOrder.uuid,
            availableSlots,
        });

        if (!selectedSlot) {
            return;
        }

        this.currentOrder.setPartner(selectedSlot.partner_id);

        args.planning_slot_id = selectedSlot;
        return super.addNewPaymentLine(paymentMethod, args);
    },
    async toggleIsToInvoice() {
        if (this.currentOrder.hasResourcePayment) {
            this.notification.add(
                _t(
                    "You cannot create an invoice for an order that will be paid with a resource-linked payment method."
                ),
                {
                    type: "warning",
                }
            );
            return;
        }
        return super.toggleIsToInvoice(...arguments);
    },
});
