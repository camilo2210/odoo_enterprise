import { SaleOrderLineProductField } from "@sale/js/sale_product_field/sale_product_field";
import { SaleLabelTextField } from "@sale/js/sale_label_text/sale_label_text";
import { patch } from "@web/core/utils/patch";

const saleSubscriptionProductMixin = () => ({
    _getAdditionalRpcParams() {
        const params = super._getAdditionalRpcParams();
        const saleOrder = this.props.record.model.root;
        if (saleOrder.data.is_subscription || saleOrder.data.subscription_state === '7_upsell') {
            params.plan_id = saleOrder.data.plan_id.id;
        } else {
            params.allow_one_time_sale = true;
        }
        return params;
    },

    _getAdditionalDialogProps() {
        const props = super._getAdditionalDialogProps();
        const saleOrder = this.props.record.model.root;
        if (saleOrder.data.is_subscription || saleOrder.data.subscription_state === '7_upsell') {
            props.plan_id = saleOrder.data.plan_id.id;
        } else {
            props.allow_one_time_sale = true;
        }
        return props;
    },
});

patch(SaleLabelTextField.prototype, saleSubscriptionProductMixin());
patch(SaleOrderLineProductField.prototype, saleSubscriptionProductMixin());
