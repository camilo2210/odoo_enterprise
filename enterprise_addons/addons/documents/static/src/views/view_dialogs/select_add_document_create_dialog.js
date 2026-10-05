import { _t } from "@web/core/l10n/translation";
import { omit } from "@web/core/utils/objects";

import { session } from "@web/session";
import { useService } from "@web/core/utils/hooks";
import {
    SelectCreateDialog,
    selectCreateDialogProps,
} from "@web/views/view_dialogs/select_create_dialog";
import { useProps, proxy, signal, t, useSubEnv } from "@odoo/owl";

export const selectAddDocumentCreateDialogProps = {
    ...selectCreateDialogProps,
    chatterParams: t.object(),
    resModel: t.string(),
    title: t.string(),
    domain: t.array().optional(),
    context: t.object().optional(),
};

export class SelectAddDocumentCreateDialog extends SelectCreateDialog {
    static template = "documents.SelectAddDocumentCreateDialog";
    props = useProps(selectAddDocumentCreateDialogProps);

    viewRef = signal.ref();

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.store = useService("mail.store");
        this.notification = useService("notification");
        this.viewState = proxy({
            type: "kanban",
        });
        const { viewState } = this;
        useSubEnv({
            config: {
                ...this.env.config,
                viewSwitcherEntries: ["kanban", "list"].map((type) => ({
                    type,
                    name: session.view_info[type].display_name,
                    icon: session.view_info[type].icon,
                    get active() {
                        return viewState.type === type;
                    },
                })),
                switchView: (type) => this.switchView(type),
            },
        });

        const { thread = {}, model, resId } = this.props.chatterParams || this.props;
        this.model = thread.model ?? model;
        this.resId = thread.id ?? resId;
    }

    get viewProps() {
        const baseProps = super.viewProps;
        const { type, folderId } = this.viewState;
        const initFolderId = isNaN(folderId) ? folderId || false : Number(folderId);
        if (this.viewContext?.documents_init_folder_id !== initFolderId) {
            this.viewContext = {
                ...baseProps.context,
                documents_init_folder_id: initFolderId,
            };
        }
        return {
            ...omit(baseProps, "forceGlobalClick", "display"),
            type,
            context: this.viewContext,
            allowSelectors: true,
            ...(type === "kanban" ? { forceGlobalClick: true } : {}),
        };
    }

    switchView(type) {
        this.viewState.folderId = this.viewRef()
            ?.querySelector(".o_search_panel_category_value_header.active")
            ?.closest("[data-value-id]")?.dataset.valueId;
        this.viewState.type = type;
    }

    get addDocumentsAttachmentMethod() {
        return this.props.chatterParams?.addDocumentsAttachment || this.addDocumentsAttachment;
    }

    get pasteDocumentsLinkMethod() {
        return this.props.chatterParams?.pasteDocumentsLink || this.pasteDocumentsLink;
    }

    get isPlugin() {
        return this.props.chatterParams?.isPlugin;
    }

    get isNewRecord() {
        return this.props.chatterParams?.isNewRecord;
    }

    /**
     * Pastes document/s share links.
     * @param {Array} resIds - List of resIDs of the selected records (documents).
     */
    async pasteDocumentsLink(resIds) {
        let response;
        try {
            response = await this.orm.read("documents.document", resIds, [
                "display_name",
                "access_url",
            ]);
        } catch (error) {
            this.notification.add(
                _t("Failed to paste link(s): ") + (error.data?.message || error.toString()),
                { type: "danger" }
            );
            this.props.close();
            return;
        }
        if (this.props.chatterParams.isFromFullComposer) {
            this.props.chatterParams.addDocumentsBus.trigger("PASTE_SHARE_LINKS", {
                links: response,
            });
        } else {
            this.addToThread(this.model, this.resId);
            const shareLinks = response
                .map(({ display_name, access_url }) => `${display_name}: ${access_url}`)
                .join("\n");
            const prefix = this.props.chatterParams.composer.composerText ? "\n" : "";
            this.props.chatterParams.composer.composerText += `${prefix}${shareLinks}`;
        }
        this.notification.add(_t("Link(s) pasted!"), { type: "success" });
        this.props.close();
    }

    /**
     * Adds the document (as an attachment) to the composer.
     * @param {Array} resIds - List of resIDs of the selected records (documents).
     */
    async addDocumentsAttachment(resIds) {
        let processedAttachments;
        try {
            // Temporary linked to the composer with id 0 to be garbage collected if not re-linked to the thread
            // (similar to what is done when uploading a file)
            const attachmentRecords = await this.orm.call(
                "documents.document",
                "add_documents_attachment",
                [resIds, "mail.compose.message", 0]
            );
            processedAttachments = await this._processAttachments(attachmentRecords);
        } catch (error) {
            this.notification.add(
                _t("Failed to add document(s): ") + (error.data?.message || error.toString()),
                { type: "danger" }
            );
            this.props.close();
            return;
        }
        const thread = this.props.chatterParams?.thread || this.addToThread(this.model, this.resId);
        const composer = this.props.chatterParams?.composer || thread.composer;

        const attachmentIds = [];
        for (const attachmentRecord of processedAttachments) {
            // Pick what the composer shows, as the media info is built for the media dialog.
            const { checksum, id, mimetype, name, type, url } = attachmentRecord;
            composer.attachments.push({
                checksum,
                extension: name.slice(Math.max(0, name.lastIndexOf(".") + 1)),
                has_thumbnail: false,
                id,
                mimetype,
                name,
                type,
                url,
            });
            attachmentIds.push(id);
        }
        this.props.chatterParams.saveRecordHandler?.(attachmentIds);
        this.props.close();
    }

    /**
     * Helper function: mainly used to convert odoo spreadsheet into .xlsx format
     */
    async _processAttachments(attachmentRecords) {
        return attachmentRecords;
    }

    /**
     * Helper method responsible to return the new thread object.
     * @param {String} currentModel - Model of the current thread.
     * @param {Number} currentChatterRecordId - ID of the current chatter record.
     */
    addToThread(currentModel, currentChatterRecordId) {
        return this.store["mail.thread"].insert({
            model: currentModel,
            id: currentChatterRecordId,
        });
    }
}

export function getAddDocumentDialogProps() {
    return {
        resModel: "documents.document",
        title: _t("Search: Documents"),
        noCreate: true,
        domain: [
            ["type", "=", "binary"],
            ["shortcut_document_id", "=", false],
        ],
        context: {
            list_view_ref: "documents.documents_view_list_add_documents_attachment",
            kanban_view_ref: "documents.documents_view_kanban_add_documents_attachment",
            documents_search_panel_no_trash: true,
            documents_view_secondary: true,
        },
    };
}
