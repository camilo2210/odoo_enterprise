import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { product_main_image_action } from "@ai_product/modules/web/product_ai_actions";

patch(FormController.prototype, {
    get aiSpecialActions() {
        const actions = super.aiSpecialActions;
        if (["product.template", "product.product"].includes(this.model.root.config.resModel)) {
            actions.product_main_image = product_main_image_action();
        }
        return actions;
    },
});
