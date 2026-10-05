import { AgentSourceAddDialog } from "@ai_agentic/components/agent_add_source_dialog/agent_add_source_dialog";
import { Domain } from "@web/core/domain";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import {
    getAddDocumentDialogProps,
    SelectAddDocumentCreateDialog,
} from "@documents/views/view_dialogs/select_add_document_create_dialog";

patch(AgentSourceAddDialog.prototype, {
    get cardsData() {
        return [
            ...super.cardsData,
            {
                image: "/ai_agentic_documents/static/img/icon.png",
                title: _t("Add from Documents"),
                onClick: () => this.onAddDocumentsSourceClick(),
            },
        ];
    },

    onAddDocumentsSourceClick() {
        const closeSelectorDialog = this.dialog.add(SelectAddDocumentCreateDialog, {
            ...getAddDocumentDialogProps(),

            title: _t("Add from Documents"),
            multiSelect: true,
            domain: (() => {
                const allowedExtensions = [
                    "pdf",
                    "docx",
                    "doc",
                    "xlsx",
                    "xls",
                    "pptx",
                    "ppt",
                    "odt",
                    "ods",
                ];
                const documentDomain = Domain.and([
                    [["type", "=", "binary"]],
                    [["file_extension", "in", allowedExtensions]],
                ]);
                return Domain.and([
                    [["shortcut_document_id", "=", false]],
                    Domain.or([[["type", "=", "folder"]], documentDomain]),
                ]).toList();
            })(),
            chatterParams: {},
            addFromDocuments: async (resIds) => {
                closeSelectorDialog();
                if (resIds.length) {
                    await this.addSelectedDocumentsToAgent(resIds);
                }
            },
        });
    },

    async addSelectedDocumentsToAgent(documentIds) {
        this.state.loading = true;
        let sources;
        try {
            sources = await this.orm.call("ai.agent.source", "create_from_selected_documents", [
                documentIds,
                this.agentId,
            ]);
        } finally {
            this.state.loading = false;
        }
        if (sources.length === 0) {
            this.notification.add(
                _t("Oops, your folder needs to contain at least one file to be used as a source!"),
                {
                    type: "danger",
                }
            );
            return;
        }
        return this.onSourcesAdded();
    },
});
