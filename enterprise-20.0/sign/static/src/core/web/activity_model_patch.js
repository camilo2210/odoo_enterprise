import { Activity } from "@mail/core/common/activity_model";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

/** @type {import("models").Activity} */
const activityPatch = {
    async goToSignableDocument() {
        if (!this.sign_request_id) return;
        const action = await this.store.env.services.orm.call(
            "sign.request",
            "go_to_signable_document",
            [[this.sign_request_id]]
        );
        this.store.env.services.action.doAction(action);
    },

    async requestSignature(template_id = false) {
        const documentReference = this.res_model && this.res_model !== "sign.request" && this.res_id 
                ? `${this.res_model},${this.res_id}` 
                : false;
        const additionalContext = {
            sign_directly_without_mail: false,
            default_activity_id: this.id,
            default_activity_type_id: this.activity_type_id.id,
            default_log_request_activity: true
        };
        if (documentReference) {
            additionalContext.default_reference_doc = documentReference;
            additionalContext.sign_from_activity = true;
            additionalContext.sign_from_record = true;
            additionalContext.default_model = this.res_model;
            additionalContext.default_res_ids = [this.res_id];
        }
        return this.store.env.services.action.doActionButton({
            type: "object",
            resModel: "sign.template",
            name:"open_sign_send_dialog",
            resIds: template_id ? [template_id] : [],
            context: additionalContext,
        });
    },

    async viewSignRequestDocuments() {
        if (!this.sign_request_id) return;

        const action = await this.store.env.services.orm.call(
            'sign.request',
            'go_to_document',
            [[this.sign_request_id]]
        );

        if (action) {
            this.store.env.services.action.doAction(action);
        }
    },

    openSignRequestForm() {
        if (!this.sign_request_id) return;
        const action = {
            type: 'ir.actions.act_window',
            res_model: 'sign.request',
            res_id: this.sign_request_id,
            views: [[false, 'form']],
            target: 'current',
        };
        this.store.env.services.action.doAction(action);
    },

    async resendSignatureAccesses() {
        if (!this.sign_request_id) return;
        await this.store.env.services.orm.call(
            "sign.request",
            "send_signature_accesses",
            [[this.sign_request_id]]
        );
        this.store.env.services.notification.add(_t("The signature request was successfully resent."), {
            type: "success",
            sticky: false,
        });
    },
};
patch(Activity.prototype, activityPatch);
