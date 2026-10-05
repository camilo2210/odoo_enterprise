import { Component, onWillUpdateProps, proxy, signal, t, useProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { RecordSelector } from "@web/core/record_selectors/record_selector";
import { _t } from "@web/core/l10n/translation";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { fileTypeMagicWordMap } from "@web/views/fields/image/image_field";
import { user } from "@web/core/user";

export const FIELD_TYPE_ICONS = {
    signature: "edit_square",
    initial: "edit_square",
    stamp: "edit_square",
    text: "text_fields",
    textarea: "menu",
    checkbox: "check_box",
    radio: "radio_button_checked",
    selection: "keyboard_arrow_down",
    strikethrough: "strikethrough_s",
    date: "calendar_today",
};

/**
 * Opens the "Add Field" dialog to create a custom sign item type, then refreshes
 * the available types and the iframe's drag-and-drop data.
 *
 * @param {Object} config
 * @param {Object} config.orm - orm service
 * @param {Object} config.action - action service
 * @param {Function} config.fetchSignItemTypes - refetches and returns the sign item types
 * @param {Object} [config.iframe] - the active document iframe to refresh
 * @param {Function} config.onFetched - receives the refreshed sign item types
 */
export async function addCustomFieldType({ orm, action, fetchSignItemTypes, iframe, onFetched }) {
    const [, viewId] = await orm.call("ir.model.data", "check_object_reference", [
        "sign",
        "sign_item_type_view_form_custom_field",
    ]);
    action.doAction(
        {
            name: _t("Add Field"),
            res_model: "sign.item.type",
            type: "ir.actions.act_window",
            views: [[viewId, "form"]],
            view_mode: "form",
            target: "new",
        },
        {
            additionalContext: {
                dialog_size: "medium",
            },
            onClose: async () => {
                const signItemTypes = await fetchSignItemTypes();
                onFetched(signItemTypes);
                setTimeout(() => {
                    if (iframe) {
                        iframe.props.signItemTypes = signItemTypes;
                        iframe.updateSignItemTypes();
                    }
                }, 100);
            },
        }
    );
}

export class SignTemplateSidebarRoleItems extends Component {
    static template = "sign.SignTemplateSidebarRoleItems";
    static components = {
        RecordSelector,
        Dropdown,
        DropdownItem,
    };
    static propsSchema = {
        signItemTypes: t.array(),
        fetchSignItemTypes: t.function(),
        iframe: t.object().optional(),
        id: t.number(),
        name: t.string(),
        signTemplateId: t.number(),
        isSignRequest: t.boolean(),
        updateRoleName: t.function(),
        roleId: t.number().optional(),
        colorId: t.number(),
        isInputFocused: t.boolean().optional(),
        isCollapsed: t.boolean(),
        updateCollapse: t.function(),
        onDelete: t.function(),
        onMoveUp: t.function(),
        onMoveDown: t.function(),
        hasMultipleSigners: t.boolean(),
        itemsCount: t.number(),
        hasSignRequests: t.boolean(),
        onFieldNameInputKeyUp: t.function(),
        assignTo: t.string().optional(),
        // Optional callbacks to lift the avatar and auth method up to the parent.
        // The mobile tabs unmount their panels on tab switch, which drops this
        // component's local state, so the parent persists these across unmounts.
        updateAssignTo: t.function().optional(),
        updateAuthMethod: t.function().optional(),
    };

    props = useProps(this.constructor.propsSchema);

    roleInputRef = signal.ref();

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.action = useService("action");
        const profilePic = this.getImageSrc(this.props.assignTo);
        this.state = proxy({
            roleName: this.props.name,
            canEditSignerName: false,
            profilePic: profilePic || "",
            signItemTypes: this.props.signItemTypes,
            isAdmin: user.isAdmin,
        });
        this.icon_type = FIELD_TYPE_ICONS;
        onWillUpdateProps((nextProps) => {
            if (nextProps.name !== this.state.roleName) {
                this.state.roleName = nextProps.name;
            }
        });
    }

    async onDeleteDialog() {
        const hasItems = this.props.itemsCount > 0;
        if (!hasItems) {
            this.props.onDelete();
        } else {
            this.dialog.add(ConfirmationDialog, {
                title: _t('Delete signer "%s"', this.state.roleName),
                body: _t("Do you really want to delete this signer?"),
                confirmLabel: _t("Delete"),
                confirm: () => {
                    this.props.onDelete();
                },
                cancel: () => {},
            });
        }
    }

    onSignerNameTextClick() {
        /* If the input is not focused, focus it. */
        if (!this.props.hasSignRequests && !this.props.isCollapsed) {
            this.state.canEditSignerName = true;
            const input = this.roleInputRef();

            const waitForVisibility = () => {
                if (input && !input.parentElement.parentElement.classList.contains("d-none")) {
                    // Input is visible, so we can focus
                    input.focus();
                    input.select();
                } else {
                    // Input is still hidden, keep checking in the next frame
                    requestAnimationFrame(waitForVisibility);
                }
            };

            waitForVisibility();
        }
    }

    onSignerNameInputBlur() {
        this.state.canEditSignerName = false;
    }

    onChangeRoleName(name) {
        // Check if the new role name is different from the current one
        if (name && this.props.roleId && name !== this.state.roleName) {
            this.state.roleName = name;
            this.props.updateRoleName(this.props.roleId, this.state.roleName);
        }
    }

    onExpandSigner(id) {
        if (this.props.isCollapsed) {
            this.props.updateCollapse(id, false);
        }
    }

    async updateRoleNameAndAvatar(data) {
        this.onChangeRoleName(data.name);
        this.props.updateAuthMethod?.(data.auth_method);
        const assignToId = data.assign_to?.id;
        if (assignToId) {
            const [partner] = await this.orm.call("res.partner", "read", [
                [assignToId],
                ["avatar_128", "avatar_1920"],
            ]);
            const avatar = partner.avatar_128?.content || partner.avatar_1920?.content;
            if (avatar) {
                this.state.profilePic = this.getImageSrc(avatar);
                this.props.updateAssignTo?.(avatar);
            }
        } else {
            this.state.profilePic = "";
            this.props.updateAssignTo?.("");
        }
    }

    async openSignRoleRecord() {
        this.dialog.add(FormViewDialog, {
            resId: this.props.roleId,
            resModel: "sign.item.role",
            size: "md",
            title: _t("Signer Settings"),
            onRecordSaved: async ({ data }) => {
                this.state.canEditSignerName = true;
                await this.updateRoleNameAndAvatar(data);
            },
        });
    }

    getImageSrc(assignTo) {
        if (!assignTo) {
            return;
        }
        const magicChar = assignTo[0];
        const format = fileTypeMagicWordMap[magicChar] || "png";
        return `data:image/${format};base64,${assignTo}`;
    }

    onAddCustomField() {
        /* Call action to add a custom field from Sign Template's sidebar. */
        return addCustomFieldType({
            orm: this.orm,
            action: this.action,
            fetchSignItemTypes: () => this.props.fetchSignItemTypes(),
            iframe: this.props.iframe,
            onFetched: (signItemTypes) => {
                this.state.signItemTypes = signItemTypes;
            },
        });
    }
}
