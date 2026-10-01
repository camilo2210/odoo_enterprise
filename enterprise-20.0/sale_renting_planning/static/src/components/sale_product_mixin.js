import { onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { SaleOrderLineProductField } from "@sale/js/sale_product_field/sale_product_field";
import { SaleLabelTextField } from "@sale/js/sale_label_text/sale_label_text";

const saleRentingPlanningProductMixin = () => ({
    setup() {
        super.setup();
        this.rentalProductConfigure = useService("rental_product_configure");

        onMounted(async () => {
            const lineId = this.props.record.resId;
            if (
                this.props.record.context.new_sale_line !== lineId ||
                this.rentalProductConfigure.hasShown(lineId)
            ) {
                return;
            }

            if (this.hasConfigurationButton) {
                this.onEditConfiguration();
                return;
            }

            // Products with no configurable attributes may still have optional products.
            // The configurator values are the authoritative source for has_optional_products,
            // and preload the data the configurator dialog needs.
            if (!this.props.record.data.product_template_id?.id) {
                return;
            }

            const data = await this._getProductConfiguratorData();
            if (data?.has_optional_products) {
                this._openProductConfigurator({ data });
            }
        });
    },
    async _openProductConfigurator({ edit = false, selectedComboItems = [], data } = {}) {
        if (
            edit
            && this.props.record.context.new_sale_line === this.props.record.resId
            && !this.rentalProductConfigure.hasShown(this.props.record.resId)
        ) {
            edit = false;
            this.rentalProductConfigure.markShown(this.props.record.resId);
            // existing data was fetched for the edit flow (`only_main_product: true`).
            // Therefore no optional products were fetched.
            data = await this._getProductConfiguratorData();
        }
        return super._openProductConfigurator({ edit, selectedComboItems, data });
    },
});

patch(SaleLabelTextField.prototype, saleRentingPlanningProductMixin());
patch(SaleOrderLineProductField.prototype, saleRentingPlanningProductMixin());
