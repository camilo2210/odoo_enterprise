import { t, useProps } from "@odoo/owl";
import { ComboConfiguratorDialog } from "@sale/js/combo_configurator_dialog/combo_configurator_dialog";
import { patch } from "@web/core/utils/patch";

patch(ComboConfiguratorDialog.prototype, {
    setup() {
        super.setup();

        this.saleSubscriptionProps = useProps({
            plan_id: t.number().optional(),
            allow_one_time_sale: t.boolean().optional(),
            subscription_plans: t.array().optional(),
        });
    },
    _getAdditionalRpcParams() {
        const params = super._getAdditionalRpcParams();
        if (this.saleSubscriptionProps.plan_id) {
            params.plan_id = this.saleSubscriptionProps.plan_id;
        }
        return params;
    },

    _getAdditionalDialogProps() {
        const props = super._getAdditionalDialogProps();
        if (this.saleSubscriptionProps.plan_id) {
            props.plan_id = this.saleSubscriptionProps.plan_id;
        }
        return props;
    },
});
