import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { WebsiteBuilder } from "@website/builder/website_builder";

patch(WebsiteBuilder.prototype, {
    async onAiChatClick() {
        const mainObject = this.websiteService.currentWebsite?.metadata?.mainObject;
        if (mainObject?.model !== "product.template" || !mainObject.id) {
            return super.onAiChatClick();
        }

        const orm = this.env.services.orm;
        const variantId = parseInt(
            this.websiteService.pageDocument
                ?.querySelector('.js_product button[name="add_to_cart"]')
                ?.dataset.productId,
            10,
        );
        const [recordModel, recordId] = variantId
            ? ["product.product", variantId]
            : ["product.template", mainObject.id];

        const applyImage = (model, id, method) => async ({ message }) => {
            const attachment = message.attachment_ids.find((a) => a.mimetype.includes("image"));
            await orm.call(model, method, [[id], attachment.id]);
            await this.editor.config.reloadEditor();
        };

        await this.env.services.aiChatLauncher.launchAIChat({
            interfaceKey: "chatter_ai_button",
            channelTitle: _t("AI Website Product Edit"),
            recordModel,
            recordId,
            aiSpecialActions: {
                product_main_image: applyImage(recordModel, recordId, "ai_set_main_image"),
                product_extra_image: applyImage("product.template", mainObject.id, "ai_add_extra_image"),
            },
        });
    },
});
