import { Component, onMounted, signal, t, useListener, useProps } from "@odoo/owl";
import { location, browser } from "@web/core/browser/browser";
import { useDebounced } from "@web/core/utils/timing";

export class KnowledgeReadOnlyHeadingLink extends Component {
    static template = "knowledge.KnowledgeReadOnlyHeadingLink";

    props = useProps({
        readonlyElementRef: t.function([], t.ref()),
    });

    headingLinkContainerRef = signal.ref();

    setup() {
        this.debouncedOnMouseMove = useDebounced(this.onMousemove.bind(this), 150);
        useListener(this.props.readonlyElementRef, "mousemove", (ev) => {
            const heading = ev.target?.closest(`:is(h1, h2, h3, h4, h5, h6)[data-heading-link-id]`);
            if (this.lastHeading !== heading) {
                this.lastHeading = heading;
                this.debouncedOnMouseMove(heading);
            }
        });

        onMounted(() => {
            // Same as HeadingLinkPlugin
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
        });
    }

    onClickLink() {
        const headingId = this.currentHeading?.getAttribute("data-heading-link-id");
        location.hash = headingId;
        browser.navigator.clipboard.writeText(location.href);
        this.highlightHeading(headingId);
    }

    onMousemove(heading) {
        if (heading?.textContent) {
            this.currentHeading = heading;
            // Resetting the position of the overlay.
            this.headingLinkContainerRef().style.top = "0px";
            this.headingLinkContainerRef().style.left = "0px";
            const containerRect = this.headingLinkContainerRef().getBoundingClientRect();
            // Get the range rectangle to position the overlay after it.
            const range = document.createRange();
            range.selectNodeContents(this.currentHeading);
            const rangeRect = range.getBoundingClientRect();
            // Position the overlay.
            this.headingLinkContainerRef().style.top = `${
                rangeRect.top -
                containerRect.top +
                (rangeRect.height - containerRect.height) / 2 +
                2
            }px`;
            this.headingLinkContainerRef().style.left = `${
                rangeRect.right - containerRect.left + 5
            }px`;
            this.headingLinkContainerRef().style.visibility = "visible";
        } else {
            this.headingLinkContainerRef().style.visibility = "hidden";
        }
    }

    highlightHeading(headingId) {
        const heading = this.props
            .readonlyElementRef()
            .querySelector(`[data-heading-link-id="${headingId}"]`);
        if (heading) {
            heading.scrollIntoView({ behavior: "smooth" });
            heading.classList.add("o-highlight-heading");
            setTimeout(() => {
                heading.classList.remove("o-highlight-heading");
            }, 2000);
        }
    }
}
