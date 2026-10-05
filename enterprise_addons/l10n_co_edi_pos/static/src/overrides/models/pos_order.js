import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    // @Override
    setup() {
        super.setup(...arguments);

        if (this.company.l10n_co_edi_pos_dian_enabled && !this.partner_id) {
            this.update({ partner_id: this.config._l10n_co_final_consumer_id });
        }
    },
});
