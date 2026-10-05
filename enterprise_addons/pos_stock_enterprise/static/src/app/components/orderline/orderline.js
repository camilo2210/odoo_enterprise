import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { Orderline } from "@pos_enterprise/app/components/orderline/orderline";

patch(Orderline.prototype, {
    get packLotLines() {
        const prepLine = this.preparation_line;
        const trackingStr = prepLine.product_id.tracking == "lot" ? _t("Lot:") : _t("SN:");
        return prepLine.pos_order_line_id?.pack_lot_ids?.map((l) => `${trackingStr} ${l.lot_name}`);
    },
});
