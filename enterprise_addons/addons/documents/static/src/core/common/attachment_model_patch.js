import { Attachment } from "@mail/core/common/attachment_model";
import { fields } from "@mail/model/export";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { url } from "@web/core/utils/urls";

/** @type {import("models").Attachment} */
const attachmentPatch = {
    setup() {
        super.setup();
        this.document_ids = fields.Many("documents.document", { inverse: "attachment_id" });
        this.linked_document_id = fields.One("documents.document");
        /** @type {number|undefined} */
        this.documentId = undefined;
        /** @type {Object|undefined} */
        this.documentData = undefined;
        this.documentEmailContent = null;
    },

    get isText() {
        return this.mimetype === "application/documents-email" || super.isText;
    },

    get urlRoute() {
        if (this.documentId) {
            return this.isImage
                ? `/web/image/${this.documentId}`
                : `/web/content/${this.documentId}`;
        }
        return super.urlRoute;
    },

    get defaultSource() {
        if (this.isPdf && this.documentId) {
            const encodedRoute = encodeURIComponent(
                url(`/documents/content/${encodeURIComponent(this.documentData.access_token)}`, {
                    download: "0",
                })
            );
            return `/web/static/lib/pdfjs/web/viewer.html?file=${encodedRoute}#pagemode=none`;
        }
        if (this.isText && this.documentId) {
            const token = encodeURIComponent(this.documentData.access_token);
            const checksum = this.documentData.checksum
                ? encodeURIComponent(this.documentData.checksum)
                : "";
            return `/documents/render_text/${token}${checksum ? `?unique=${checksum}` : ""}`;
        }
        return super.defaultSource;
    },

    get urlQueryParams() {
        const res = super.urlQueryParams;
        if (this.documentId) {
            res["model"] = "documents.document";
            return res;
        }
        return res;
    },

    get documentIcon() {
        return !this.linked_document_id
            ? "storage"
            : this.id === this.linked_document_id.attachment_id.id
            ? "link"
            : "folder";
    },

    get documentHelperText() {
        return this.linked_document_id ? _t("Organize in Documents") : _t("Add to Documents");
    },
};
patch(Attachment.prototype, attachmentPatch);
