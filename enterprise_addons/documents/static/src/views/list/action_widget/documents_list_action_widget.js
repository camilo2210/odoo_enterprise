import { Component, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

export class DocumentsListActionWidget extends Component {
    props = useProps(standardWidgetProps);
    static template = "documents.DocumentsListActionWidget";

    setup() {
        this.documentService = useService("document.document");
    }

    get actionItems() {
        return [
            {
                name: "deepSearch",
                icon: "search",
                description: _t("Search in Folder"),
                isVisible: () =>
                    this.props.record.data.active && this.props.record.data.type === "folder",
                onActionClicked: () =>
                    this.env.searchModel.deepSearchFolder(this.props.record.data.id),
            },
            {
                name: "share",
                icon: "share",
                description: _t("Share"),
                isVisible: () =>
                    this.props.record.isActive &&
                    this.documentService.userIsInternal &&
                    this.documentService.isFolderSharable(this.props.record.data),
                onActionClicked: () =>
                    this.documentService.openSharingDialog([this.props.record.data.id]),
            },
            {
                name: "download",
                icon: "download",
                description: _t("Download"),
                isVisible: () => this.props.record.data.type !== "request",
                onActionClicked: () => this.documentService.downloadDocuments([this.props.record]),
            },
            {
                name: "edit",
                icon: "edit",
                description: _t("Rename"),
                isVisible: () =>
                    this.props.record.isActive &&
                    this.documentService.isEditable(this.props.record.data),
                onActionClicked: async () => {
                    await this.documentService.openDocumentFormDialog({
                        documentId: this.props.record.data.id,
                    });
                    await this.env.model._notifyChange();
                },
            },
            {
                name: "details",
                icon: "info",
                description: _t("Details"),
                isVisible: () => this.documentService.userIsInternal,
                onActionClicked: async () => {
                    if (this.documentService.focusedRecord.id !== this.props.record.id) {
                        this.documentService.focusRecord(this.props.record);
                        if (!this.documentService.state.rightPanelVisible) {
                            this.documentService.toggleRightPanelVisibility();
                        }
                    } else {
                        this.documentService.toggleRightPanelVisibility();
                    }
                },
            },
            {
                name: "open",
                icon: "login",
                description: _t("Go inside"),
                isVisible: () => this.props.record.data.type === "folder",
                onActionClicked: () => this.props.record.openFolder(),
            },
        ];
    }
}

export const documentsListActionWidget = {
    component: DocumentsListActionWidget,
};

registry.category("view_widgets").add("documents_list_actions", documentsListActionWidget);
