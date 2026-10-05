import { FileViewer } from "@documents/core/web/document_file_viewer";
import { Component, signal, t, useListener, useProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class DocumentsFileViewer extends Component {
    static template = "documents.DocumentsFileViewer";
    static components = {
        FileViewer,
    };

    props = useProps({
        previewStore: t.object(),
    });

    rootRef = signal.ref();

    setup() {
        this.documentService = useService("document.document");

        const onKeydown = this.onIframeKeydown.bind(this);

        // We need to wait until the iframe is loaded to be able to bind our keydown handler.
        useListener(
            () => this.rootRef()?.querySelector("iframe"),
            "load",
            function onLoad(ev) {
                const iframe = ev.currentTarget;
                // In case of youtube links contentDocument might be null.
                if (iframe.contentDocument) {
                    iframe.contentDocument.addEventListener("keydown", onKeydown);
                }
            }
        );
    }

    get isRightPanelVisible() {
        return this.documentService.state.rightPanelVisible && this.documentService.canShowRightPanel;
    }

    onGlobalKeydown(ev) {
        // Some keydown events are not handled by the fileViewer as we want them too
        // making it possible to interact with the background.
        const cancelledKeys = ["ArrowUp", "ArrowDown"];
        if (cancelledKeys.includes(ev.key)) {
            ev.stopPropagation();
        }
    }

    onIframeKeydown(ev) {
        if (ev.key === "Escape") {
            this.env.model.env.documentsView.bus.trigger("documents-close-preview");
        }
    }
}
