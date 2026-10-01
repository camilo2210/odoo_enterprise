import { Component, signal, t, useListener, useProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class DocumentsDropZone extends Component {
    static template = "documents.DocumentsDropZone";

    props = useProps({
        parentRoot: t.any(), // Parent's root element, used to know the zone to use.
    });

    dragOver = signal(false);
    topOffset = signal(0);

    setup() {
        this.documentService = useService("document.document");
        useListener(this.props.parentRoot, "dragover", this.onDragOver.bind(this));
        useListener(this.props.parentRoot, "dragleave", this.onDragLeave.bind(this));
        useListener(this.props.parentRoot, "scroll", () => {
            this.topOffset.set(this.props.parentRoot().scrollTop);
        });
    }

    get root() {
        return this.props.parentRoot;
    }

    get canDrop() {
        return this.documentService.canUploadInFolder(this.env.searchModel.getSelectedFolder());
    }

    get rootDropOverClass() {
        return this.canDrop ? "o_documents_drop_over" : "o_documents_drop_over_unauthorized";
    }

    onDragOver(ev) {
        if (
            !ev.dataTransfer.types.includes("Files") ||
            ev.dataTransfer.types.includes("o_documents_data")
        ) {
            return;
        }
        ev.stopPropagation();
        ev.preventDefault();

        this.root?.()?.classList.toggle(this.rootDropOverClass, true);
        this.dragOver.set(true);
    }

    onDragLeave(ev) {
        ev.stopPropagation();
        ev.preventDefault();

        this.root?.()?.classList.remove(this.rootDropOverClass);
        this.dragOver.set(false);
    }

    onDrop(ev) {
        if (!ev.dataTransfer.types.includes("Files")) {
            return;
        }

        this.root?.()?.classList.remove(this.rootDropOverClass);
        this.dragOver.set(false);
        if (this.canDrop) {
            this.env.documentsView.bus.trigger("documents-upload-files", {
                files: ev.dataTransfer.files,
                accessToken: this.documentService.currentFolderAccessToken,
            });
        }
    }
}
