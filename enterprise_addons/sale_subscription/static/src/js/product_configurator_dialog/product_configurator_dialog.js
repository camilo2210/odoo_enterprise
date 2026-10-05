import { ProductConfiguratorDialog } from "@sale/js/product_configurator_dialog/product_configurator_dialog";
import { proxy, t, useProps } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { useSubEnv } from "@web/owl2/utils";

// Bridge between the dialog and the CartService patch (website_sale_subscription).
// The dialog writes the selected plan here before confirming,
// then CartService reads it in _makeRequest to inject the plan_id.
export const subscriptionDialogState = { cartPlanId: null };


patch(ProductConfiguratorDialog.prototype, {
    setup() {
        super.setup();

        this.saleSubscriptionProps = useProps({
            plan_id: t.number().optional(),
            allow_one_time_sale: t.boolean().optional(),
        });

        this.subscriptionState = proxy({
            selectedPlanId: this.saleSubscriptionProps.plan_id || null,
            // Locked when a plan was pre-chosen (on a parent subscription product page,
            // or an existing subscription in the cart). If neither, the user
            // picks the plan inline from the optional-product dropdown.
            lockedPlanId: this.saleSubscriptionProps.plan_id || null,
        });
        useSubEnv({
            subscriptionState: this.subscriptionState,
            setSubscriptionPlan: this._setSubscriptionPlan.bind(this),
        });
    },

    async _loadData() {
        const result = await super._loadData(...arguments);
        if (result.locked_plan_id && !this.subscriptionState.lockedPlanId) {
            this.subscriptionState.lockedPlanId = result.locked_plan_id;
            this.subscriptionState.selectedPlanId = result.locked_plan_id;
        }
        if (!this.subscriptionState.selectedPlanId) {
            const firstSub = result.optional_products?.find((p) => p.subscription_plans?.length);
            if (firstSub) {
                this.subscriptionState.selectedPlanId = firstSub.subscription_plans[0].id;
            }
        }
        return result;
    },

    _getAdditionalRpcParams() {
        const params = super._getAdditionalRpcParams();
        if (this.subscriptionState?.selectedPlanId) {
            params.plan_id = this.subscriptionState.selectedPlanId;
        }
        if (this.saleSubscriptionProps.allow_one_time_sale) {
            params.allow_one_time_sale = true;
        }
        return params;
    },

    async onConfirm(options) {
        subscriptionDialogState.cartPlanId = this.subscriptionState?.selectedPlanId || null;
        try {
            return await super.onConfirm(options);
        } finally {
            subscriptionDialogState.cartPlanId = null;
        }
    },

    async _setSubscriptionPlan(planId) {
        this.subscriptionState.selectedPlanId = planId;
        for (const product of [...this.state.products, ...this.state.optionalProducts]) {
            if (!product.subscription_plans?.length) continue;
            Object.assign(
                product,
                await this._updateCombination(product, product.quantity, product.uom.id)
            );
        }
    },
});
