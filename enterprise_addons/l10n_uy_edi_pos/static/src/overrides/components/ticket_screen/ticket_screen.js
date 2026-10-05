import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(TicketScreen.prototype, {
    l10nUyGetCfeState(order) {
        return {
            received: _t("Waiting for DGI"),
            accepted: _t("Accepted"),
            rejected: _t("Rejected"),
            error: _t("Error"),
        }[order.l10n_uy_edi_cfe_state];
    },

    // @Override
    setPartnerToRefundOrder(partner, destinationOrder) {
        if (this.pos.isUruguayanCompany()) {
            const destinationPartner = destinationOrder.getPartner();
            if (
                partner &&
                (!destinationPartner ||
                    destinationPartner.id === this.pos.config._l10n_uy_consumidor_final_id)
            ) {
                destinationOrder.setPartner(partner);
            }
        } else {
            super.setPartnerToRefundOrder(...arguments);
        }
    },
});
