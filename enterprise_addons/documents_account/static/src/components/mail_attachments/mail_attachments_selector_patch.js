import { AccountMoveSendAttachmentsSelector } from "@account/components/mail_attachments/account_move_send_attachments_selector";
import { HtmlMailField } from "@mail/views/web/fields/html_mail_field/html_mail_field";
import { _t } from "@web/core/l10n/translation";
import { createElementWithContent } from "@web/core/utils/html";
import { patch } from "@web/core/utils/patch";
import { useBus, useService } from "@web/core/utils/hooks";
import {
    getAddDocumentDialogProps,
    SelectAddDocumentCreateDialog,
} from "@documents/views/view_dialogs/select_add_document_create_dialog";

/** * Helper function to format document share links into clickable HTML. */
function formatLinks(links) {
    const container = document.createElement("div");
    for (const { display_name, access_url } of links) {
        const link = createElementWithContent("a", display_name);
        link.href = access_url;
        link.target = "_blank";
        link.className = "d-block";
        container.append(link);
    }
    return container;
}

/** * Patches HtmlMailField to listen for the PASTE_SHARE_LINKS event.
 * This injects the document URLs directly into the editor of the send wizard.
 */
patch(HtmlMailField.prototype, {
    setup() {
        super.setup(...arguments);
        if (this.props.record.resModel === "account.move.send.wizard" && this.props.name === "body") {
            useBus(this.props.record.model.bus, "PASTE_SHARE_LINKS", ({ detail }) => {
                this.editor.shared.dom.insert(formatLinks(detail.links));
                this.editor.editable.focus();
                this.editor.shared.history.commit();
            });
        }
    },
});

/** * Patches AccountMoveSendAttachmentsSelector to add the "Add from Documents" logic.
 * Bridges the accounting send wizard attachment selector with the Documents app.
 */
patch(AccountMoveSendAttachmentsSelector.prototype, {
    setup() {
        super.setup(...arguments);
        this.dialog = useService("dialog");
        this.orm = useService("orm");
        this.notification = useService("notification");
    },

    /** Opens the Document selector popup with the shared configuration. */
    addDocumentsAttachment() {
        const { data } = this.props.record;
        const closeDialog = this.dialog.add(SelectAddDocumentCreateDialog, {
            ...getAddDocumentDialogProps(),
            chatterParams: {
                model: data.model,
                resId: JSON.parse(data.res_ids || "[]")[0],
                isPlugin: true,
                pasteDocumentsLink: (resIds) => this._pasteDocumentsLinks(resIds, closeDialog),
                saveRecordHandler: (attachmentIds) => this._saveDocumentsAttachments(attachmentIds),
            },
        });
    },

    /** Fetches the access URLs of the selected documents and triggers the paste event. */
    async _pasteDocumentsLinks(resIds, close) {
        try {
            const links = await this.orm.read("documents.document", resIds, ["display_name", "access_url"]);
            this.props.record.model.bus.trigger("PASTE_SHARE_LINKS", { links });
            this.notification.add(_t("Links pasted"), { type: "success" });
        } catch (error) {
            this.notification.add(
                _t("Failed to paste links: ") + (error.data?.message || error.toString()),
                { type: "danger" }
            );
        }
        close();
    },

    /** Converts the selected Documents into standard mail attachments on the record. */
    async _saveDocumentsAttachments(attachmentIds) {
        const attachments = await this.orm.read("ir.attachment", attachmentIds, ["name", "mimetype"]);
        this.props.record.update({
            [this.props.name]: this.attachments.concat(
                attachments.map((attachment) => ({
                    id: attachment.id,
                    name: attachment.name,
                    mimetype: attachment.mimetype,
                    placeholder: false,
                    manual: true,
                }))
            ),
        });
    },
});
