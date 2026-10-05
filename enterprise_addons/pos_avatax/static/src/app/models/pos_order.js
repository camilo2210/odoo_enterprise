import { patch } from "@web/core/utils/patch";
import { PosOrder } from "@point_of_sale/app/models/pos_order";

patch(PosOrder.prototype, {
    // @override
    findFiscalPosition(fiscalPosition) {
        // ignore fiscal postion using AvaTax if AvaTax is not enabled in POS and if not in the allowed list
        if (
            !this.config.module_pos_avatax &&
            fiscalPosition?.is_avatax &&
            !this.config.fiscal_position_ids.some((fp) => fp.id === fiscalPosition.id)
        ) {
            return false;
        }
        return super.findFiscalPosition(fiscalPosition);
    },
});
