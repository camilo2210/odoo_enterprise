import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import { SignTemplate } from "@sign/backend_components/sign_template/sign_template_action";
import { SignTemplateSidebarRoleItems } from "@sign/backend_components/sign_template/sign_template_sidebar_role_items";

function emsignerWarning(dialog) {
    dialog.add(ConfirmationDialog, {
        title: _t("Warning"),
        body: _t("Aadhaar Sign works only with a single signer and document. Adding more will switch to the standard eSignature."),
        confirmLabel: _t("Ok"),
    });
}

patch(SignTemplate.prototype, {
    // Hide the "Add Document" button while any role signs with emsigner.
    get canAddDocument() {
        return super.canAddDocument && !this.state.signers.some((signer) => signer.auth_method === "emsigner");
    },

    async updateDocuments() {
        await super.updateDocuments();
        if (await this.orm.call("sign.template", "check_emsigner_constraint", [this.signTemplate.id])) {
            emsignerWarning(this.dialog);
        }
    },
});

patch(SignTemplateSidebarRoleItems.prototype, {
    async openSignRoleRecord() {
        this.dialog.add(FormViewDialog, {
            resId: this.props.roleId,
            resModel: "sign.item.role",
            size: "md",
            title: _t("Signer Edition"),
            onRecordSaved: async ({ data }) => {
                await this.updateRoleNameAndAvatar(data);
                if (await this.orm.call("sign.template", "check_emsigner_constraint", [this.props.signTemplateId])) {
                    emsignerWarning(this.dialog);
                }
            },
        });
    },
});
