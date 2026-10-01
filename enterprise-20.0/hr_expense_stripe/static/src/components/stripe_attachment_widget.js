import { Component, t, useProps } from "@odoo/owl";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class stripeAttachment extends Component {
    static template = "hr_expense_stripe.stripeAttachment";

    props = useProps({
        ...standardFieldProps,
        purpose: t.string(),
        title: t.string().optional(),
    });

    setup() {
        this.dialog = useService("dialog");
    }

    get isReadOnly() {
        return this.props.readonly;
    }

    get isFilePresent() {
        const fileData = this.props.record.data[this.props.name];
        return Boolean(fileData);
    }

    get isDownloadable() {
        return ![
            "account_requirement",
            "platform_terms_of_service",
            "additional_verification",
        ].includes(this.props.purpose);
    }

    async uploadFile(event) {
        const file = event.target.files[0];
        if (!file) {
            return;
        }

        const base64File = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result.split(",")[1]);
            reader.onerror = (error) => reject(error);
            reader.readAsDataURL(file);
        });
        if (!base64File) {
            return;
        }

        const record = this.props.record;
        if (!record.resId || record.dirty) {
            const saved = await record.save();
            if (!saved) return;
        }

        await rpc("/stripe_issuing/upload_file", {
            model: record.resModel,
            record_id: record.resId,
            field_name: this.props.name,
            purpose: this.props.purpose,
            file_name: file.name,
            b64_file_data: base64File,
            content_type: file.type,
        });
        await record.load();
    }

    downloadFile() {
        const params = new URLSearchParams({
            model: this.props.record.resModel,
            record_id: this.props.record.resId,
            field_name: this.props.name,
        });
        window.open(`/stripe_issuing/download_file?${params.toString()}`, "_blank");
    }

    deleteFile() {
        this.dialog.add(ConfirmationDialog, {
            title: _t("Confirm Deletion"),
            body: _t("Are you sure you want to delete this attachment?"),
            confirmLabel: _t("Delete"),
            cancelLabel: _t("Discard"),
            confirm: () => {
                this.props.record.update({ [this.props.name]: false });
            },
            cancel: () => {},
        });
    }
}

export const stripeAttachmentWidget = {
    supportedTypes: ["char"],
    component: stripeAttachment,
    extractProps: ({ attrs }) => ({ purpose: attrs.purpose, title: attrs.title }),
};

registry.category("fields").add("stripe_attachment", stripeAttachmentWidget);
