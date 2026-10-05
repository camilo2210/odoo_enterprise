import { t, useProps } from "@odoo/owl";
import { ProductConfiguratorDialog } from "@sale/js/product_configurator_dialog/product_configurator_dialog";
import { patch } from "@web/core/utils/patch";

patch(ProductConfiguratorDialog.prototype, {
    setup() {
        super.setup();

        this.saleRentingProps = useProps({
            start_date: t.string().optional(),
            end_date: t.string().optional(),
        });
    },
    _getAdditionalRpcParams() {
        const params = super._getAdditionalRpcParams();
        if (this.saleRentingProps.start_date && this.saleRentingProps.end_date) {
            params.start_date = this.saleRentingProps.start_date;
            params.end_date = this.saleRentingProps.end_date;
        }
        return params;
    },
});
