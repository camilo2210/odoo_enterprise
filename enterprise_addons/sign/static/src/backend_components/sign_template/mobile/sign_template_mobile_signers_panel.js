import { t } from "@odoo/owl";
import { SignTemplateSidebar } from "@sign/backend_components/sign_template/sign_template_sidebar";
import { SignTemplateMobileSignerRow } from "./sign_template_mobile_signer_row";

/**
 * The mobile Signers tab. Signer management (add, delete with its dialog,
 * move, rename focus handling, etc...) is fully inherited from the desktop sidebar.
 * Only the presentation differs.
 */
export class SignTemplateMobileSignersPanel extends SignTemplateSidebar {
    static template = "sign.SignTemplateMobileSignersPanel";
    static components = {
        ...SignTemplateSidebar.components,
        SignTemplateMobileSignerRow,
    };

    static propsSchema = {
        signers: t.array(),
        activeSignerId: t.number(),
        updateActiveSigner: t.function(),
        pushNewSigner: t.function(),
        hasSignRequests: t.boolean(),
        signTemplateId: t.number(),
        updateRoleName: t.function(),
        deleteRole: t.function(),
        updateSigners: t.function(),
        moveSignerUp: t.function(),
        moveSignerDown: t.function(),
    };

    async onClickAddSigner() {
        await super.onClickAddSigner();
        this.props.updateActiveSigner(this.props.signers.at(-1).id);
    }

    getSignerRowProps(id) {
        const signer = this.props.signers.find((signer) => signer.id === id);
        return {
            id: id,
            name: signer.name,
            signTemplateId: this.props.signTemplateId,
            roleId: signer.roleId,
            colorId: signer.colorId,
            itemsCount: signer.itemsCount,
            hasSignRequests: this.props.hasSignRequests,
            hasMultipleSigners: this.props.signers.length > 1,
            updateRoleName: this.props.updateRoleName,
            assignTo: signer.assignTo,
            updateAssignTo: (assignTo) => {
                signer.assignTo = assignTo;
            },
            updateAuthMethod: (authMethod) => {
                signer.auth_method = authMethod;
            },
            onDelete: () => this.deleteSigner(id, signer.roleId),
            onMoveUp: () => this.onMoveSignerUp(id),
            onMoveDown: () => this.onMoveSignerDown(id),
            onFieldNameInputKeyUp: (ev) => this.onFieldNameInputKeyUp(ev),
            isActive: signer.id === this.props.activeSignerId,
            onSelect: () => this.props.updateActiveSigner(id),
        };
    }
}
