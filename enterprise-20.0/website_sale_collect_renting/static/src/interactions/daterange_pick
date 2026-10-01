import { patch } from "@web/core/utils/patch";
import { patchDynamicContent } from "@web/public/utils";
import { DaterangePicker } from "@website_sale_renting/interactions/daterange_picker";

patch(DaterangePicker.prototype, {
    setup() {
        super.setup();
        patchDynamicContent(this.dynamicContent, {
            _root: {
                "t-on-reload_product_availabilities": () =>
                    this._updateRentingProductAvailabilities(true),
            },
        });
    },
});
