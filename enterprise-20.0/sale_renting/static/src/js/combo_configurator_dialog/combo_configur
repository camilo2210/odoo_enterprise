import { t, useProps } from "@odoo/owl";
import { ComboConfiguratorDialog } from "@sale/js/combo_configurator_dialog/combo_configurator_dialog";
import { patch } from "@web/core/utils/patch";

patch(ComboConfiguratorDialog.prototype, {
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

    _getAdditionalDialogProps() {
        const props = super._getAdditionalDialogProps();
        if (this.saleRentingProps.start_date && this.saleRentingProps.end_date) {
            props.start_date = this.saleRentingProps.start_date;
            props.end_date = this.saleRentingProps.end_date;
        }
        return props;
    },
});
