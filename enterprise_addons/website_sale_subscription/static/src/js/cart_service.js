import { CartService } from '@website_sale/js/cart_service';
import { patch } from '@web/core/utils/patch';
import { subscriptionDialogState } from '@sale_subscription/js/product_configurator_dialog/product_configurator_dialog';

patch(CartService.prototype, {
    async _makeRequest(params) {
        if (!params.plan_id && subscriptionDialogState.cartPlanId) {
            params = { ...params, plan_id: subscriptionDialogState.cartPlanId };
        }
        return super._makeRequest(params);
    },
});
