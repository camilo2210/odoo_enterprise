import { registry } from "@web/core/registry";
import { Base } from "@point_of_sale/app/models/related_models";

// We don't use the POS order model here to avoid loading PosOrderAccounting,
// accountTaxHelpers, and other dependencies. We can use it if we need more of its methods in future.
export class PosOrder extends Base {
    static pythonModel = "pos.order";

    get presetDateTime() {
        return this.preset_time?.isValid
            ? this.preset_time.hasSame(this.date_order, "day")
                ? this.formatDateOrTime("preset_time", "time")
                : this.formatDateOrTime("preset_time")
            : false;
    }
}

registry.category("pos_available_models").add(PosOrder.pythonModel, PosOrder);
