import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { product_extra_image_action } from "@ai_website_sale/modules/web/product_ai_actions";

patch(FormController.prototype, {
    get aiSpecialActions() {
        const actions = super.aiSpecialActions;
        if (["product.template", "product.product"].includes(this.model.root.config.resModel)) {
            actions.product_extra_image = product_extra_image_action();
        }
        return actions;
    },
});
