import { Component, proxy, signal, t, useProps } from "@odoo/owl";
import { getCssFromPaperFormat } from "@web_studio/client_action/report_editor/utils";
import { useThrottleForAnimation } from "@web/core/utils/timing";
import { ErrorDisplay } from "@web_studio/client_action/report_editor/error_display";

export class ReportEditorIframe extends Component {
    static components = { ErrorDisplay };
    static template = "web_studio.ReportEditor.Iframe";
    props = useProps({
        iframeSource: t.string().optional(),
        onIframeLoaded: t.function().optional(),
    });

    iframeRef = signal.ref();

    setup() {
        this.reportEditorModel = proxy(this.env.reportEditorModel);
        this.onContainerScroll = useThrottleForAnimation(() => {
            if (this.iframeRef()?.contentDocument) {
                this.iframeRef().contentDocument.dispatchEvent(new Event("scroll"));
            }
        });
    }

    get paperFormatStyle() {
        const {
            margin_top,
            margin_left,
            margin_right,
            print_page_height,
            print_page_width,
            header_spacing,
        } = this.reportEditorModel.paperFormat;
        const marginTop = Math.max(0, (margin_top || 0) - (header_spacing || 0));
        return getCssFromPaperFormat({
            margin_top: marginTop,
            margin_left,
            margin_right,
            print_page_height,
            print_page_width,
        });
    }
    get iframeStyle() {
        const { print_page_height } = this.reportEditorModel.paperFormat;
        return getCssFromPaperFormat({ print_page_height });
    }

    get iframeSource() {
        return this.props.iframeSource || this.reportEditorModel.reportHtml;
    }

    get iframeKey() {
        return this.reportEditorModel.renderKey + "_" + (this.iframeSource || "");
    }

    async onIframeLoaded() {
        await this.resizeIframeContent({ iframeRef: this.iframeRef });
        this.props.onIframeLoaded?.({ iframeRef: this.iframeRef });
        this.reportEditorModel.setInEdition(false);
    }

    async resizeIframeContent({ iframeRef }) {
        const paperFormat = this.reportEditorModel.paperFormat;
        const iframeEl = iframeRef();
        const iframeContent = iframeEl.contentDocument;

        // zoom content from 96 (default browser DPI) to paperformat DPI
        const zoom = 96 / paperFormat.dpi;
        Array.from(iframeContent.querySelector("main")?.children || []).forEach((el) => {
            let sectionZoom = zoom;
            if (!paperFormat.disable_shrinking) {
                const { width } = el.getBoundingClientRect();
                sectionZoom = Math.min(zoom, width / el.scrollWidth);
            }
            el.setAttribute("oe-origin-style", el.getAttribute("style") || "");
            el.style.setProperty("zoom", sectionZoom);
        });

        // TODO: it seems that the paperformat doesn't exactly do that
        // this.$content.find('.header').css({
        //     'margin-bottom': (this.paperFormat.header_spacing || 0) + 'mm',
        // });
        // TODO: won't be pretty if the content is larger than the format

        const footer = iframeContent.querySelector(".footer");
        const footerStyle = footer?.style;
        if (footerStyle) {
            const { width } = iframeContent.querySelector(".page")?.getBoundingClientRect() || {};
            if (!footer.hasAttribute("oe-origin-style")) {
                footer.setAttribute("oe-origin-style", footer.getAttribute("style") || "");
            }
            if (width) {
                footerStyle.setProperty("width", `${width}px`);
            }
        }

        const html = iframeContent.querySelector("html");
        if (html) {
            html.style.overflow = "hidden";
        }

        // set the size of the iframe
        const proms = [];
        Array.from(iframeContent.querySelectorAll("img[src]") || []).forEach((img) => {
            if (img.complete) {
                return;
            }
            const prom = new Promise((resolve) => {
                img.onload = resolve;
            });
            proms.push(prom);
        });
        await Promise.all(proms);

        // WHY --> so that after the load of the iframe, if there are images,
        // the iframe height is recomputed to the height of the content images included
        if (iframeEl && iframeContent && iframeContent.body) {
            iframeEl.style.height = iframeContent.body.scrollHeight + "px";
        }
    }
}
