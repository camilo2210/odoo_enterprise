import { ProductVariantPreview } from "@website_sale/interactions/product/product_variant_preview";
import { registry } from "@web/core/registry";

class AIPreviewVariantPreview extends ProductVariantPreview {
    static selector = ".o_ai_preview_cards";

    setup() {
        this.margin = 4;
        // Cards are injected dynamically; defer measurement until layout is computed.
        requestAnimationFrame(this.protectSyncAfterAsync(() => this.updateVariantPreview()));
    }
}

registry
    .category("public.interactions")
    .add("ai_website_sale_livechat.product_variant_preview", AIPreviewVariantPreview);
