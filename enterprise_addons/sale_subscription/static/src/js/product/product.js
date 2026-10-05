import { Component, t, useProps } from '@odoo/owl';
import { Product, productProps } from '@sale/js/product/product';
import { patch } from '@web/core/utils/patch';

export class SubscriptionPlanSelector extends Component {
    static template = 'sale_subscription.SubscriptionPlanSelector';
    props = useProps({
        plans: t.array(),
        selectedPlanId: t.any().optional(),
        isLocked: t.boolean(),
    });
    onChange(ev) {
        this.env.setSubscriptionPlan(parseInt(ev.target.value));
    }
}

Object.assign(productProps, {
    subscription_plans: t.array().optional(),
});

patch(Product, {
    components: { ...Product.components, SubscriptionPlanSelector },
});
