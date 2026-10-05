import configuratorTourUtils from '@sale/js/tours/product_configurator_tour_utils';

function assertOptionalSubscriptionPlan(productName, planName) {
    return {
        content: `Assert that ${productName} has the ${planName} plan selected`,
        trigger: `
            ${configuratorTourUtils.optionalProductSelector(productName)}
            td.o_sale_product_configurator_price
            select:has(option:checked:contains("${planName}"))
        `,
    };
}

export default {
    assertOptionalSubscriptionPlan,
};
