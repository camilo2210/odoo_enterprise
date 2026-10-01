import { Plugin } from "@html_editor/plugin";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";

export const EXTERNAL_IMAGE_TO_SAVE_CLASS = "o_external_image_to_save";

// External image URLs inside a CSS `url()`, e.g. `background-image: url("https://…")`.
const CSS_URL_RE = /url\(\s*['"]?([^'")\s]+)['"]?\s*\)/gi;
// A srcset is a comma separated list of `<url> [descriptor]` candidates.
const SRCSET_CANDIDATE_RE = /(?:^|,)\s*([^\s,]+)/g;

/**
 * Copies external images into Odoo attachments when the page is saved.
 *
 * A page that references an image on someone else's server breaks as soon as that
 * server removes it, starts blocking hotlinks or goes away, and it silently sends
 * visitors to a third party. Instead we want to save the images as attachements.
 *
 * Only elements flagged with {@link EXTERNAL_IMAGE_TO_SAVE_CLASS} are considered: the
 * download makes the server fetch a caller-provided URL, so it stays opt-in per image
 * instead of scanning the whole editable on every save.
 */
export class ExternalImageSavePlugin extends Plugin {
    static id = "externalImageSave";
    static shared = ["markExternalImages", "localizeExternalImages"];

    /** @type {import("plugins").WebsiteResources} */
    resources = {
        on_will_save_handlers: this.localizeExternalImages.bind(this),
    };

    /**
     * Flag every element of `rootEl` pointing at an image hosted elsewhere, so that
     * {@link localizeExternalImages} copies it into Odoo on the next save.
     *
     * @param {HTMLElement|DocumentFragment} rootEl
     */
    markExternalImages(rootEl) {
        const selector = "img[src], img[srcset], [style]";
        for (const el of rootEl.querySelectorAll(selector)) {
            if (this.getExternalImageUrls(el).length) {
                el.classList.add(EXTERNAL_IMAGE_TO_SAVE_CLASS);
            }
        }
    }

    /**
     * Download the flagged external images into attachments and point the elements at
     * the local copies.
     *
     * A URL that cannot be downloaded keeps its external value and its flag, so the
     * page still renders and a later save tries again; failing the save instead would
     * lose the user's work over a third-party server being slow.
     *
     * @param {HTMLElement} [editableEl]
     */
    async localizeExternalImages(editableEl = this.editable) {
        const els = [...editableEl.querySelectorAll(`.${EXTERNAL_IMAGE_TO_SAVE_CLASS}`)];
        const urls = new Set(els.flatMap((el) => this.getExternalImageUrls(el)));
        if (!urls.size) {
            // Nothing external left: the images were replaced or removed since they
            // were flagged.
            this.clearFlags(els);
            return;
        }

        let sources = {};
        let errors = {};
        try {
            ({ sources = {}, errors = {} } = await rpc("/ai_website/localize_external_images", {
                urls: [...urls],
            }));
        } catch {
            this.notifyFailures(urls.size);
            return;
        }

        for (const el of els) {
            this.remapUrls(el, sources);
        }
        // Keep the flag only where an external URL survived, so the next save retries it.
        this.clearFlags(els.filter((el) => !this.getExternalImageUrls(el).length));
        const failureCount = Object.keys(errors).length;
        if (failureCount) {
            this.notifyFailures(failureCount);
        }
    }

    clearFlags(els) {
        for (const el of els) {
            el.classList.remove(EXTERNAL_IMAGE_TO_SAVE_CLASS);
        }
    }

    notifyFailures(count) {
        this.services.notification.add(
            _t(
                "%s image(s) are still hosted on another website and may stop working. You can save again to retry saving them.",
                count
            ),
            { type: "warning" }
        );
    }

    /**
     * @param {HTMLElement} el
     * @returns {string[]} the external image URLs of `el`, as written in the document
     */
    getExternalImageUrls(el) {
        const urls = [
            el.getAttribute("src"),
            ...this.matchAll(el.getAttribute("srcset"), SRCSET_CANDIDATE_RE),
            ...this.matchAll(el.style.backgroundImage, CSS_URL_RE),
        ];
        return urls.filter((url) => this.isExternalUrl(url));
    }

    matchAll(value, regex) {
        return value ? [...value.matchAll(regex)].map((match) => match[1]) : [];
    }

    /**
     * Replace the external URLs of `el` by the local ones of `sources`, keyed by
     * absolute URL.
     *
     * @param {HTMLElement} el
     * @param {Object.<string, string>} sources
     */
    remapUrls(el, sources) {
        for (const url of this.getExternalImageUrls(el)) {
            const localUrl = sources[this.resolveUrl(url)];
            if (!localUrl) {
                continue;
            }
            for (const attribute of ["src", "srcset"]) {
                const value = el.getAttribute(attribute);
                if (value?.includes(url)) {
                    el.setAttribute(attribute, value.replaceAll(url, localUrl));
                }
            }
            if (el.style.backgroundImage.includes(url)) {
                el.style.backgroundImage = el.style.backgroundImage.replaceAll(url, localUrl);
            }
        }
    }

    /**
     * An image is external when it is served over HTTP(S) by another origin than the
     * website itself. Relative URLs, `data:` and `blob:` sources are already local or
     * cannot be downloaded, and are left alone.
     */
    isExternalUrl(url) {
        const resolvedUrl = url && this.resolveUrl(url);
        if (!resolvedUrl) {
            return false;
        }
        const { protocol, origin } = new URL(resolvedUrl);
        return ["http:", "https:"].includes(protocol) && origin !== this.document.location.origin;
    }

    resolveUrl(url) {
        try {
            return new URL(url, this.document.location.href).href;
        } catch {
            return undefined;
        }
    }
}

registry.category("website-plugins").add(ExternalImageSavePlugin.id, ExternalImageSavePlugin);
