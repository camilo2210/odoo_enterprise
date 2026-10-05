import { expect, test } from "@odoo/hoot";
import { animationFrame, click, waitFor } from "@odoo/hoot-dom";
import { registry } from "@web/core/registry";
import { contains, patchWithCleanup } from "@web/../tests/web_test_helpers";
import { getDragHelper, waitForEndOfOperation } from "@html_builder/../tests/helpers";
import {
    defineWebsiteModels,
    setupWebsiteBuilder,
} from "@website/../tests/builder/website_helpers";

defineWebsiteModels();

test("dropping image snippet and clicking AI button keeps placeholder", async () => {
    // Mock aiChatLauncher service to avoid RPCs and complex setup
    const aiChatLauncher = registry.category("services").get("aiChatLauncher");
    patchWithCleanup(aiChatLauncher, {
        start() {
            return {
                launchAIChat: async () => ({ id: "test_thread", channel: {} }),
            };
        },
    });

    // The text is added to introduce a drop zone for snippets.
    await setupWebsiteBuilder(`<div><p>Text</p></div>`);

    // Drag the snippet from the sidebar to the content
    const { moveTo, drop } = await contains(
        ".o-website-builder_sidebar [name='Image'] .o_snippet_thumbnail"
    ).drag();
    await moveTo(":iframe .oe_drop_zone");
    await drop(getDragHelper());

    // Verify media dialog opens
    await animationFrame();
    await waitFor(".o_select_media_dialog");
    expect(".o_select_media_dialog").toHaveCount(1);

    // Click the AI button
    await click("button[title='Generate Image with AI']");
    await animationFrame();

    // Verify media dialog is closed
    expect(".o_select_media_dialog").toHaveCount(0);

    // Verify snippet is dropped (not discarded)
    await waitForEndOfOperation();
    expect("[data-snippet='s_image']").toHaveCount(1);
});
