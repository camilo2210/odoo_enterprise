import { render } from "@web/owl2/utils";
import { Component, proxy, t, useProps } from "@odoo/owl";
import { SignTemplateSidebarRoleItems } from "./sign_template_sidebar_role_items";
import { useService } from "@web/core/utils/hooks";
import { useSignViewButtons } from "@sign/views/hooks";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { getDataURLFromFile } from "@web/core/utils/urls";

export class SignTemplateSidebar extends Component {
    static template = "sign.SignTemplateSidebar";
    static components = {
        SignTemplateSidebarRoleItems,
        Dropdown,
        DropdownItem,
    };
    static propsSchema = {
        canAddDocument: t.boolean().optional(),
        deleteDocument: t.function(),
        deleteRole: t.function(),
        documents: t.array(),
        fetchSignItemTypes: t.function(),
        hasSignRequests: t.boolean(),
        iframe: t.object().optional(),
        isSignRequest: t.boolean(),
        moveDocumentDown: t.function(),
        moveDocumentUp: t.function(),
        moveSignerDown: t.function(),
        moveSignerUp: t.function(),
        onEditTemplate: t.function(),
        onUpdateDocument: t.function(),
        pushNewSigner: t.function(),
        saveManually: t.function(),
        selectedDocumentId: t.number(),
        signItemTypes: t.array(),
        signTemplateId: t.number(),
        signers: t.array(),
        updateCollapse: t.function(),
        updateDocumentName: t.function(),
        updateDocuments: t.function(),
        updateRoleName: t.function(),
        updateSelectedDocument: t.function(),
        updateSigners: t.function(),
    };

    props = useProps(this.constructor.propsSchema);

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.state = proxy({
            editableDocumentId: false,
        });
        this.signButtons = useSignViewButtons();
    }

    focusOnNewAddedSigner(roleId) {
        const spanSelector = `span[data-role-id="${roleId}"]`;
        const inputSelector = `input[data-role-id="${roleId}"]`;

        // Polling function to check if the input is available in the DOM
        const checkInput = () => {
            const span = document.querySelector(spanSelector);
            const input = document.querySelector(inputSelector);

            // If the span and input are found, focus on input
            if (span && input) {
                span.click();
                input.focus();
                input.select();
            } else {
                // If input is not found, wait for the next frame and check again
                requestAnimationFrame(checkInput);
            }
        };

        checkInput();
    }

    async onClickAddSigner() {
        await this.props.pushNewSigner();
        this.focusOnNewAddedSigner(this.props.signers.at(-1).roleId);
    }

    deleteSigner(signerId, roleId) {
        const updatedSigners = [...this.props.signers].filter((signer) => signer.id != signerId);

        /* After deleting the signer, if no signer is focused, focus the last one in the array. */
        if (!updatedSigners.some((signer) => !signer.isCollapsed) && updatedSigners.length > 0) {
            updatedSigners[updatedSigners.length - 1].isCollapsed = false;
        }

        this.props.updateSigners(updatedSigners);
        this.props.deleteRole(roleId);
    }

    getSidebarRoleItemsProps(id) {
        //  TODO MASTER: we should put the role name here. it would prevent one rpc per role...
        const signer = this.props.signers.find((signer) => signer.id === id);
        return {
            id: id,
            name: signer.name,
            signTemplateId: this.props.signTemplateId,
            roleId: signer.roleId,
            colorId: signer.colorId,
            signItemTypes: this.props.signItemTypes,
            isSignRequest: this.props.isSignRequest,
            updateRoleName: this.props.updateRoleName,
            isCollapsed: signer.isCollapsed,
            isInputFocused: signer.isInputFocused,
            iframe: this.props.iframe,
            /* Update callbacks binding for parent props: */
            fetchSignItemTypes: () => this.props.fetchSignItemTypes(),
            updateCollapse: (id, value) => this.props.updateCollapse(id, value),
            onDelete: () => this.deleteSigner(id, signer.roleId),
            onMoveUp: () => this.onMoveSignerUp(id),
            onMoveDown: () => this.onMoveSignerDown(id),
            hasMultipleSigners: this.props.signers.length > 1,
            onFieldNameInputKeyUp: (ev) => this.onFieldNameInputKeyUp(ev),
            itemsCount: signer.itemsCount,
            hasSignRequests: this.props.hasSignRequests,
            assignTo: signer.assignTo,
            updateAssignTo: (assignTo) => {
                signer.assignTo = assignTo;
            },
            updateAuthMethod: (authMethod) => {
                signer.auth_method = authMethod;
            },
        };
    }

    onDocumentNameBlur() {
        this.state.editableDocumentId = false;
    }

    onFieldNameInputKeyUp(ev) {
        if (ev.key === "Enter") {
            ev.target.blur();
        }
    }

    onUpdateSelectedDocument(documentId) {
        this.props.updateSelectedDocument(documentId);
    }

    onDocumentNameChanged(documentId, e) {
        const documentName = e.target.value;
        if (documentName) {
            this.props.updateDocumentName(documentId, documentName);
        }
    }

    setEditableDocumentId(documentId) {
        this.state.editableDocumentId = documentId;
        this.props.updateSelectedDocument(documentId);
    }

    onDocumentNameTextClick(documentId) {
        this.state.editableDocumentId = documentId;
        const input = document.querySelector(`[data-document-id="${documentId}"]`);

        // Polling function to check if the input is no longer `d-none`
        const waitForVisibility = () => {
            if (input && !input.classList.contains("d-none")) {
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

    async onRemoveDocument(documentId) {
        await this.props.deleteDocument(documentId);
        render(this);
    }

    async onMoveDocumentUp(documentId) {
        await this.props.moveDocumentUp(documentId);
        render(this);
    }

    async onMoveDocumentDown(documentId) {
        await this.props.moveDocumentDown(documentId);
        render(this);
    }

    async onMoveSignerUp(signerId) {
        await this.props.moveSignerUp(signerId);
        render(this);
    }

    async onMoveSignerDown(signerId) {
        await this.props.moveSignerDown(signerId);
        render(this);
    }

    async onUpdateDocument(documentId, ev) {
        /* Check if pdf got uploaded, save manually, and call update document function from props. */
        const file = ev.target.files && ev.target.files.length && ev.target.files[0];
        if (!file) {
            return;
        }
        if (this.props.saveManually) {
            await this.props.saveManually();
        }
        const url = await getDataURLFromFile(file);
        const fileData = {
            name: file.name,
            raw: url.split(",")[1],
        };
        await this.props.onUpdateDocument(documentId, fileData);
    }
}
