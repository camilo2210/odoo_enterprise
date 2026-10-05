import { mailPopoutService } from "@mail/core/common/mail_popout_service";
import { patch } from "@web/core/utils/patch";

function waitForStylesheet(link) {
    if (link.sheet) {
        return Promise.resolve();
    }
    return new Promise((resolve) => {
        link.addEventListener("load", resolve, { once: true });
        link.addEventListener("error", resolve, { once: true });
    });
}

const popoutPatch = {
    async addAssets(externalWindow) {
        await super.addAssets(...arguments);
        const externalDocument = externalWindow.document;
        for (const node of window.document.head.childNodes) {
            if (node instanceof HTMLLinkElement && node.relList.contains("manifest")) {
                continue;
            }
            externalDocument.head.append(node.cloneNode(true));
        }
        await Promise.all(
            [...externalDocument.querySelectorAll('link[rel~="stylesheet"]')].map(waitForStylesheet)
        );
        await externalDocument.fonts.ready;
    },
};

patch(mailPopoutService, popoutPatch);
