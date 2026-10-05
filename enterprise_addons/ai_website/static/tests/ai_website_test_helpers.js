import { queryOne } from "@odoo/hoot-dom";
import { loadBundle } from "@web/core/assets";
import { setupWebsiteBuilder } from "@website/../tests/builder/website_helpers";

export async function setupAiWebsiteBuilder(websiteContent, options = {}) {
    const { openEditor = true, ...rest } = options;
    const result = await setupWebsiteBuilder(websiteContent, { ...rest, openEditor: false });
    const targetDoc = queryOne(":iframe");
    await loadBundle("ai_website.ai_assets", { targetDoc });
    await loadBundle("ai_website.ai_editor_assets", { targetDoc });
    if (openEditor) {
        await result.openBuilderSidebar();
    }
    return result;
}
