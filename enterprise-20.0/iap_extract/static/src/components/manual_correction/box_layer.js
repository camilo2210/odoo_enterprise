import { Box } from "@iap_extract/components/manual_correction/box";
import { BoxCluster } from "@iap_extract/components/manual_correction/box_cluster";
import { Component, proxy, signal, t, useListener, useProps } from "@odoo/owl";

export class BoxLayer extends Component {
    static components = { Box, BoxCluster };
    static template = "iap_extract.BoxLayer";

    props = useProps({
        boxes: t.array(),
        boxClusters: t.array(),
        pageLayer: t.customValidator(
            t.object(),
            (pageLayer) => pageLayer?.nodeType === Node.ELEMENT_NODE
        ),
        onClickBoxCallback: t.function(),
        onMouseHoverBoxCallback: t.function(),
        onClickBoxClusterCallback: t.function(),
        onBoxesSelectionCallback: t.function(),
        mode: t.string(),
    });

    boxLayerRef = signal.ref();

    setup() {
        this.state = proxy({
            boxes: this.props.boxes,
            boxClusters: this.props.boxClusters,
            isSelecting: false,
            selectionStart: { x: 0, y: 0 },
            selectionEnd: { x: 0, y: 0 },
        });

        // Used to define the style of the contained boxes
        if (this.isOnPDF) {
            this.pageWidth = this.props.pageLayer.style.width;
            this.pageHeight = this.props.pageLayer.style.height;

            // Get the scrollable element of the PDF viewer to listen to scroll events
            this.viewerScrollableEl =
                this.props.pageLayer.ownerDocument.getElementById("viewerContainer");
            useListener(this.viewerScrollableEl, "scroll", this.onScroll.bind(this));
        } else if (this.isOnImg) {
            this.viewerScrollableEl = this.props.pageLayer.parentElement;
            useListener(this.viewerScrollableEl, "scroll", this.onScroll.bind(this));
            this.pageWidth = `${this.props.pageLayer.clientWidth}px`;
            this.pageHeight = `${this.props.pageLayer.clientHeight}px`;
        }
    }

    checkAndHighlightBoxes() {
        const { selectionStart, selectionEnd } = this.state;
        const selectionRect = {
            left: Math.min(selectionStart.x, selectionEnd.x),
            top: Math.min(selectionStart.y, selectionEnd.y),
            right: Math.max(selectionStart.x, selectionEnd.x),
            bottom: Math.max(selectionStart.y, selectionEnd.y),
        };

        for (const boxEl of this.boxLayerRef().getElementsByClassName("o_extract_mixin_box")) {
            const boxId = parseInt(boxEl.dataset.id, 10);
            const matchedBox = this.props.boxes.find((box) => box.id === boxId);
            const boxRect = boxEl.getBoundingClientRect();

            const isOverlapping = !(
                boxRect.right < selectionRect.left ||
                boxRect.left > selectionRect.right ||
                boxRect.bottom < selectionRect.top ||
                boxRect.top > selectionRect.bottom
            );
            matchedBox.isHighlighted = isOverlapping;
        }
    }

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    get style() {
        if (this.isOnPDF) {
            return [
                `width: ${this.props.pageLayer.style.width}`,
                `height: ${this.props.pageLayer.style.height}`,
            ].join(";");
        } else if (this.isOnImg) {
            return [
                `width: ${this.props.pageLayer.clientWidth}px`,
                `height: ${this.props.pageLayer.clientHeight}px`,
                `left: ${this.props.pageLayer.offsetLeft}px`,
                `top: ${this.props.pageLayer.offsetTop}px`,
            ].join(";");
        }
    }

    get selectionStyle() {
        const { selectionStart, selectionEnd } = this.state;
        const x1 = Math.min(selectionStart.x, selectionEnd.x);
        const y1 = Math.min(selectionStart.y, selectionEnd.y);
        const x2 = Math.max(selectionStart.x, selectionEnd.x);
        const y2 = Math.max(selectionStart.y, selectionEnd.y);

        return `
            left: ${x1}px;
            top: ${y1}px;
            width: ${x2 - x1}px;
            height: ${y2 - y1}px;
        `;
    }

    get isOnImg() {
        return this.props.mode === "img";
    }

    get isOnPDF() {
        return this.props.mode === "pdf";
    }

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    onMouseDown(event) {
        this.state.isSelecting = true;
        this.state.selectionStart = { x: event.clientX, y: event.clientY };
        this.state.selectionEnd = { x: event.clientX, y: event.clientY };
        if (this.viewerScrollableEl) {
            this.scrollX = this.viewerScrollableEl.scrollLeft;
            this.scrollY = this.viewerScrollableEl.scrollTop;
        }
    }

    onMouseUp(event) {
        if (!this.state.isSelecting) {
            return;
        }

        this.state.isSelecting = false;

        this.checkAndHighlightBoxes();

        const selectedBoxes = this.props.boxes.filter((box) => box.isHighlighted);
        this.props.onBoxesSelectionCallback(selectedBoxes);

        this.props.boxes.forEach((box) => (box.isHighlighted = false));
        this.state.selectionStart = { x: 0, y: 0 };
        this.state.selectionEnd = { x: 0, y: 0 };
    }

    onMouseMove(event) {
        if (!this.state.isSelecting) {
            return;
        }
        this.state.selectionEnd = { x: event.clientX, y: event.clientY };
        this.checkAndHighlightBoxes();
    }

    onScroll(event) {
        if (this.state.isSelecting) {
            // Adjust the selection on scroll
            const scrollX = this.viewerScrollableEl.scrollLeft;
            const scrollY = this.viewerScrollableEl.scrollTop;

            this.state.selectionStart.x += this.scrollX - scrollX;
            this.state.selectionStart.y += this.scrollY - scrollY;

            this.scrollX = scrollX;
            this.scrollY = scrollY;
        }
    }
}
