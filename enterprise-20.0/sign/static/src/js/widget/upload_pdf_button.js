/** @odoo-module */

import { registry } from "@web/core/registry";
import { Component, t, useProps } from "@odoo/owl";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { _t } from "@web/core/l10n/translation";
import { useSignViewButtons } from "@sign/views/hooks";

export class UploadPdfButton extends Component {
    static template = "sign.upload_pdf_button";

    props = useProps({
        ...standardWidgetProps,
        title: t.string().optional(),
        btnClass: t.string().optional(),
        options: t.object().optional(),
    });

    setup() {
        this.signButtons = useSignViewButtons();
    }

    onClickUpload(context) {
        // Set `resModel` to 'sign.template' as it is required by the file upload logic
        // to properly associate the uploaded files with the correct model.
        this.props.resModel = "sign.template";
        const modelContext = this.env.model?.config?.context; // Environment context of the model initiating the upload action
        const extraContext = {}; // Additional context built from record data and provided options
        const options = this.props.options || {};
        const recordData = this.props.record.data;
        const referenceDoc = recordData.reference_doc ?? modelContext?.default_reference_doc;
        if (referenceDoc) {
            const { resModel, resId } = referenceDoc;
            if (resModel && resId) {
                extraContext.default_reference_doc = `${resModel},${resId}`;
            } else if (typeof referenceDoc === "string") {
                extraContext.default_reference_doc = referenceDoc;
            }
        }

        extraContext.no_default_signer =
            options.no_default_signer ??
            recordData.no_default_signer ??
            modelContext?.no_default_signer;

        extraContext.default_log_request_activity =
            options.default_log_request_activity ??
            recordData.log_request_activity ??
            modelContext?.default_log_request_activity;

        extraContext.default_activity_type_id =
            (recordData.activity_type_id?.id || recordData.activity_type_id) ??
            modelContext?.default_activity_type_id;

        return this.signButtons.requestFile(context, extraContext);
    }
}

export const uploadPdfButton = {
    component: UploadPdfButton,
    extractProps: ({ attrs, options }) => ({
        title: attrs.title || _t("Upload PDF"),
        btnClass: attrs.btnClass || "btn btn-link",
        options: options || {},
    }),
};

registry.category("view_widgets").add("upload_pdf_button", uploadPdfButton);
