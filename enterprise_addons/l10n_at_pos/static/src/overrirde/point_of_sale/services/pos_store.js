import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

patch(PosStore.prototype, {
    canEditPayment(order) {
        return this.company.l10n_at_is_fon_authenticated ? false : super.canEditPayment(order);
    },
});
