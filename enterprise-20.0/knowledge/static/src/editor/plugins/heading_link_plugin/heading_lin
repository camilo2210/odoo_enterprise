import { Plugin } from "@html_editor/plugin";
import { location, browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { ancestors, closestElement, descendants } from "@html_editor/utils/dom_traversal";
import { xml } from "@odoo/owl";
import { renderToElement } from "@web/core/utils/render";
import { uuid } from "@web/core/utils/strings";
import { debounce } from "@web/core/utils/timing";

export class HeadingLinkPlugin extends Plugin {
    static id = "headingLink";
    static dependencies = ["localOverlay", "history"];
    resources = {
        /** Handlers */
        on_editor_started_handlers: this.onStartEdition.bind(this),
        on_element_split_handlers: ({ secondPart }) => this.onAfterSplitElement(secondPart),

        /** Processors */
        clean_for_save_processors: (root) => this.cleanForSave(root),
        normalize_processors: (root) => this.updateHeadingIds(root),
        before_insert_processors: this.ensureIdUniqueness.bind(this),

        system_classes: ["o-highlight-heading"],
    };

    setup() {
        // Create an overlay with the anchor.
        this.headingLinkOverlay = this.dependencies.localOverlay.makeLocalOverlay("o-heading-link-overlay");
        this.headingLinkContainer = renderToElement(xml`
            <div class="d-flex">
                <a href="#" title="${_t("Copy a link to this heading to the clipboard")}" class="o-heading-link px-1 rounded bg-100 text-400">
                    <i class="oi" data-icon="link" aria-hidden="true"/>
                </a>
            </div>
        `);
        this.headingLink = this.headingLinkContainer.firstElementChild;
        this.headingLinkOverlay.append(this.headingLinkContainer);
        this.headingLinkOverlay.style.visibility = "hidden";
        this.addDomListener(this.headingLink, "click", () => {
            const headingId = this.currentHeading?.getAttribute("data-heading-link-id");
            // Navigate to the heading and add the url to the clipboard.
            location.hash = headingId;
            browser.navigator.clipboard.writeText(location.href);
            // Commit the history and make sure the ID is saved.
            this.dependencies.history.commit();
            // Highlight the heading.
            this.highlightHeading(headingId);
        });
        this.addDomListener(this.headingLink, "dragstart", ev => ev.preventDefault());

        this.debouncedOnMouseMove = debounce(this.onMousemove.bind(this), 150);
        this.addDomListener(
            this.editable,
            "mousemove",
            (ev) => {
                const heading = ev.target
                    ? closestElement(ev.target, `:is(h1, h2, h3, h4, h5, h6)[data-heading-link-id]`)
                    : undefined;
                if (this.lastHeading !== heading) {
                    this.lastHeading = heading;
                    this.debouncedOnMouseMove(heading);
                }
            },
            true
        );
        this.updateHeadingIds();
    }

    onStartEdition() {
        if (location.hash) {
            const headingId = location.hash.replace(/^#/, "");
            if (headingId) {
                // Wait until the browser has rendered the editor before
                // scrolling. The timeout value of 500 is a little arbitrary,
                // but it should be enough to prevent an irritating case where
                // a Youtube video is in the document and loads while the
                // autoscroll is happening, and stops it.
                setTimeout(() => {
                    this.highlightHeading(headingId);
                }, 500);
            }
        }
    }

    onMousemove(heading) {
        if (heading?.textContent) {
            this.currentHeading = heading;
            // Resetting the position of the overlay.
            this.headingLinkOverlay.style.top = "0px";
            this.headingLinkOverlay.style.left = "0px";
            const containerRect = this.headingLinkContainer.getBoundingClientRect();
            // Get the range rectangle to position the overlay after it.
            const range = this.document.createRange();
            range.selectNodeContents(this.currentHeading);
            const rangeRect = range.getBoundingClientRect();
            // Position the overlay.
            this.headingLinkOverlay.style.top = `${rangeRect.top - containerRect.top + ((rangeRect.height - containerRect.height) / 2) + 2}px`;
            this.headingLinkOverlay.style.left = `${rangeRect.right - containerRect.left + 5}px`;
            this.headingLinkOverlay.style.visibility = "visible";
        } else {
            this.headingLinkOverlay.style.visibility = "hidden";
        }
    }

    cleanForSave(root) {
        for (const el of root.querySelectorAll(".o-highlight-heading")) {
            el.classList.remove("o-highlight-heading");
        }
        return root;
    }

    destroy() {
        this.debouncedOnMouseMove.cancel();
        super.destroy();
    }

    /**
     * Always reset the `data-heading-link-id` when inserting a heading which
     * already has one.
     */
    ensureIdUniqueness(insertContainer) {
        for (const heading of insertContainer.querySelectorAll("[data-heading-link-id]")) {
            heading.dataset.headingLinkId = uuid();
        }
        return insertContainer;
    }

    onAfterSplitElement(secondPart) {
        // Ensure the ID doesn't get cloned.
        secondPart?.removeAttribute("data-heading-link-id");
    }

    /**
     * @param {Element} [root]
     */
    updateHeadingIds(root = this.editable) {
        const headings = [root, ...ancestors(root, this.editable), ...descendants(root)]
            .filter(node => node && /^H\d$/.test(node.nodeName));
        for (const heading of [...new Set(headings)]) {
            const headingId = heading.getAttribute("data-heading-link-id");
            if (!headingId) {
                heading.setAttribute("data-heading-link-id", uuid());
            }
        }
        return root;
    }

    highlightHeading(headingId) {
        const heading = this.editable.querySelector(`[data-heading-link-id="${headingId}"]`);
        if (heading) {
            heading.scrollIntoView({ behavior: "smooth" });
            heading.classList.add("o-highlight-heading");
            setTimeout(() => {
                heading.classList.remove("o-highlight-heading");
            }, 2000);
        }
    }
}
