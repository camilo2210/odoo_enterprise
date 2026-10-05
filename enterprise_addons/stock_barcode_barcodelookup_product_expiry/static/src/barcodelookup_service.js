import { BarcodeLookupServiceClass } from "@stock_barcode_barcodelookup/barcodelookup_service";
import { patch } from "@web/core/utils/patch";

patch(BarcodeLookupServiceClass.prototype, {
    updateContextFromRule(context, rule) {
        super.updateContextFromRule(...arguments);
        if (rule.type === "expiration_date") {
            context["default_use_expiration_date"] = true;
        }
    }
});
