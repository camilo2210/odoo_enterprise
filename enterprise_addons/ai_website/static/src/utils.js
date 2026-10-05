import { browser } from "@web/core/browser/browser";
import { getData } from "@ai/utils/bus_data_getter";

export const AI_EDITABLE_ZONE_SELECTORS = {
    main: "div#wrap",
    footer: "footer#bottom > #footer",
};

export const AI_WEBSITE_ELEMENT_SELECTION_COMMAND = "AI Website: Element Selection Command";
export const AI_WEBSITE_ELEMENT_SELECTION_STATE = "AI Website: Element Selection State";
export const AI_WEBSITE_TYPING_TIMEOUT = 180_000; // 3 minutes

const DATA_POLL_ATTEMPTS = 50;
const DATA_POLL_INTERVAL = 200;

/**
 * While waiting for the builder to mount, we keep calling getData until we get a response or we
 * give up.
 */
export async function pollForData(dataSource) {
    for (let attempt = 0; attempt < DATA_POLL_ATTEMPTS; attempt++) {
        const data = await getData(dataSource);
        if (data) {
            return data;
        }
        await new Promise((resolve) => browser.setTimeout(resolve, DATA_POLL_INTERVAL));
    }
    return null;
}

export function isEditorSidebarOpen(websiteService) {
    return websiteService.context.edition;
}

/**
 * Currently, a page is editable by the website builder AI if it exists in the
 * website.page model. Which is not the case for controller-rendered pages like
 * /shop or /blog.
 */
export function isPageAiEditable(websiteService) {
    const model = websiteService.currentWebsite?.metadata?.mainObject?.model;
    return model === "website.page" || model === "product.template";
}

export function isAiWebsiteBuilderChannel(channel) {
    return channel?.aiRootSession?.ai_composer_id?.interface_key === "website_builder_ai";
}

export function getScriptTitle(scriptEl) {
    const humanReadableTitle = scriptEl.dataset.aiScriptId.split("--")[0];
    const title = humanReadableTitle.replaceAll("_", " ");
    return title[0].toUpperCase() + title.slice(1);
}
