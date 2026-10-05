import { t } from "@odoo/owl";
import { SignTemplateSidebarRoleItems } from "@sign/backend_components/sign_template/sign_template_sidebar_role_items";

/**
 * One signer row of the mobile Signers tab. Behavior (rename, signer settings
 * dialog, delete confirmation, avatar handling, etc...) is fully inherited from the
 * desktop sidebar component. Only the presentation differs.
 */
export class SignTemplateMobileSignerRow extends SignTemplateSidebarRoleItems {
    static template = "sign.SignTemplateMobileSignerRow";

    static propsSchema = {
        id: t.number(),
        name: t.string(),
        signTemplateId: t.number(),
        roleId: t.number(),
        colorId: t.number(),
        itemsCount: t.number(),
        hasSignRequests: t.boolean(),
        hasMultipleSigners: t.boolean(),
        updateRoleName: t.function(),
        onDelete: t.function(),
        onMoveUp: t.function(),
        onMoveDown: t.function(),
        onFieldNameInputKeyUp: t.function(),
        assignTo: t.string().optional(),
        updateAssignTo: t.function().optional(),
        updateAuthMethod: t.function().optional(),
        isActive: t.boolean(),
        onSelect: t.function(),
    };
}
