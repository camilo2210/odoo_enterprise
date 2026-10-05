import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { SignTemplateControlPanel } from "./sign_template_control_panel";
import { SignTemplateBody } from "./sign_template_body";
import { Component, onWillStart, proxy, useProps } from "@odoo/owl";
import { standardActionServiceProps } from "@web/webclient/actions/action_plugin";
import { SignTemplateSidebar } from "./sign_template_sidebar";
import { SignTemplateMobileShell } from "./mobile/sign_template_mobile_shell";
import { rpc } from "@web/core/network/rpc";
import { useSetupAction } from "@web/search/action_hook";
import { makeDraggableHook } from "@web/core/utils/draggable_hook_builder_owl";
import {
    startHelperLines,
    startEdgeScroll,
    draggingHelperFunctions,
    getOffsetFromIframe,
    getIframeViewerContainer,
    getIframeContainer,
} from "@sign/components/sign_request/utils";
import { clamp } from "@web/core/utils/numbers";

export class SignTemplate extends Component {
    static template = "sign.Template";
    static components = {
        SignTemplateControlPanel,
        SignTemplateBody,
        SignTemplateSidebar,
        SignTemplateMobileShell,
    };

    props = useProps(standardActionServiceProps);

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.uiService = useService("ui");
        const params = this.props.action.params;
        this.templateID = params.id;
        const name = this.props.action.name || params.name;

        if (this.templateID) {
            this.props.updateActionState({ id: this.templateID });
        }
        if (name) {
            this.env.config.setDisplayName(name);
            this.props.updateActionState({ name: name });
        }
        this.actionType = params.sign_edit_call || "";
        this.resModel = params.resModel || "";
        this.referenceDoc = this.props.action.context.default_reference_doc;
        this.activityId = this.props.action.context.default_activity_id;
        this.noDefaultSigner = this.props.action.context.no_default_signer;
        this.logRequestActivity = this.props.action.context.default_log_request_activity;
        this.defaultActivityTypeId = this.props.action.context.default_activity_type_id;
        this.signStatus = proxy({
            isTemplateChanged: false,
            // isSignTemplateSaved is used as a flag to know if the template is saved or not.
            // It is used to show a notification when the user tries to edit the uploaded document.
            // It is set to true when the template is saved from the backend.
            isSignTemplateSaved: this.resModel === "sign.request" ? true : false,
            save: () => {},
            discardChanges: () => {},
            isDiscardingChanges: false,
        });
        this.signStatus.discardChanges = () => this.discardChanges();

        onWillStart(async () => {
            if (!this.templateID) {
                return this.goBackToKanban();
            }
            return Promise.all([this.fetchTemplateData(), this.fetchFont()]);
        });
        this.state = proxy({
            signers: [],
            nextId: 0,
            documentIds: [],
            selectedDocumentId: 0,
            activeSignerId: 0,
            iframe: undefined,
        });
        this.waitForIframeToLoad();

        useSetupAction({
            beforeLeave: async () => {
                if (
                    this.signStatus.isTemplateChanged &&
                    !this.signStatus.isSignTemplateSaved &&
                    this.signTemplate.active
                ) {
                    await this.signStatus.save();
                    this.notification.add(_t("Saved"), { type: "success" });
                }
                // When the user clicks on "discard" from the status indicator, do not show the confirmation dialog.
                else if (!this.signTemplate.active && !this.signStatus.isDiscardingChanges) {
                    /* When user is directly sending a document for signing by clicking
                    on the 'Send' or 'Sign Now' button from wizard, we don't want to show the confirmation dialog. */
                    const isSignRequest = await this.orm.searchCount(
                        "sign.request",
                        [["template_id", "=", this.signTemplate.id]],
                        { limit: 1 }
                    );
                    return isSignRequest || this.showConfirmationDialog();
                }
                this.isDiscardingChanges = false;
            },
        });

        this.bodyIframes = {};
        this.startDragAndDrop();
    }

    // ===== Begin Drag Logic =====

    /**
     * Sets up dragging for:
     * - Sign field buttons in the main document
     * - Sign items inside the iframe
     *
     * Uses the draggable framework from Odoo. Also sets up dragging helpers
     * to control the drag visuals.
     */
    startDragAndDrop() {
        this.signButtonSelector = "o_sign_field_type_button";
        this.signItemSelector = "o_sign_sign_item";
        this.signItemDragConditions = ":not(.o_resizing):not(.multi_selected)";
        this.iframeSelector = "o_sign_pdf_iframe";
        this.draggingHelpers = draggingHelperFunctions();
        this.draggingRef = () => document.body;
        makeDraggableHook({
            name: "useSignDraggable",
            onWillStartDrag: this.onWillStartDrag.bind(this),
            onDragStart: this.onDragStart.bind(this),
            onDrag: this.onDrag.bind(this),
            onDrop: this.onDrop.bind(this),
            onDragEnd: this.onDragEnd.bind(this),
        })({
            iframeSelector: `.${this.iframeSelector}`,
            ref: this.draggingRef,
            elements: `.${this.signButtonSelector}, .${this.signItemSelector}${this.signItemDragConditions}`,
        });
    }

    /**
     * Returns the currently active document iframe.
     *
     * @returns {HTMLIFrameElement|null} The active document iframe, or null if none is found.
     */
    getActiveBodyIframe() {
        return this.bodyIframes[this.state.selectedDocumentId] || null;
    }

    /**
     * Translates a point into coordinates relative to the pdf iframe, based
     * on its source frame, given by `view`. Coordinates measured in the main
     * window are shifted by the iframe position, while coordinates already
     * relative to the iframe are returned as is.
     *
     * @param {{x: number, y: number, view?: Window}} point
     * @returns {{x: number, y: number}}
     */
    getIframeOffset({ x, y, view }) {
        return (view || window) === window
            ? getOffsetFromIframe(getIframeContainer(), x, y)
            : { x, y };
    }

    /**
     * Translates the dragging pointer position into coordinates relative to
     * the pdf viewer container, for the edge scrolling.
     *
     * @param {{x: number, y: number, view?: Window}} pointer
     * @returns {{x: number, y: number}}
     */
    getEdgeScrollOffset(pointer) {
        const { x, y } = this.getIframeOffset(pointer);
        const viewerRect = getIframeViewerContainer(this.currIframe).getBoundingClientRect();
        return { x: x - viewerRect.left, y: y - viewerRect.top };
    }

    /**
     * Positions the given element at the pointer location, while ensuring it stays
     * within the bounds of the dragging container.
     *
     * @param {HTMLElement} element - The element to position.
     * @param {number} x - The x-coordinate of the pointer.
     * @param {number} y - The y-coordinate of the pointer.
     * @param {Function} addStyle - A callback used to apply positioning styles to the element.
     */
    positionElementWithinDraggingContainer(element, x, y, addStyle) {
        const containerRect = this.draggingInsideIframe
            ? getIframeViewerContainer(this.currIframe).getBoundingClientRect()
            : this.draggingRef().getBoundingClientRect();
        const elementRect = element.getBoundingClientRect();

        let left, top;
        if (this.draggingInsideIframe) {
            // Keep the relative offset between pointer and element (no element resizing)
            left = elementRect.left;
            top = elementRect.top;
        } else {
            /**
             * Centers the element on the pointer.
             * When dragging a sign field button, the ghost element may be resized based on the PDF page dimensions,
             * which can cause it to shift away from the pointer. This function corrects that by centering it.
             */
            left = x - elementRect.width / 2;
            top = y - elementRect.height / 2;
        }

        // Clamp the 'left' and 'top' positions to ensure the element stays within the container's boundaries.
        left = clamp(
            left,
            containerRect.left,
            containerRect.left + containerRect.width - elementRect.width
        );
        top = clamp(
            top,
            containerRect.top,
            containerRect.top + containerRect.height - elementRect.height
        );

        addStyle(element, {
            left: `${left}px`,
            top: `${top}px`,
        });
    }

    /**
     * Sets up the necessary preparations right before dragging starts.
     *
     * @param {Object} param0 - Parameters passed by the dragging framework.
     * @param {HTMLElement} param0.ctx - The context of the dragging session.
     * @param {Function} param0.addCleanup - Function to add dragging cleanups.
     * @returns {void}
     */
    onWillStartDrag({ ctx, addCleanup }) {
        const element = ctx.current.element;
        this.isDraggingActive = this.getActiveBodyIframe() && element;
        if (!this.isDraggingActive) {
            return;
        }

        this.currIframe = this.getActiveBodyIframe();
        this.currIframe.closePopover();
        this.currIframe.resetSelection(); // Resets the multi-selected elements when dragging an element that is not currently selected
        this.helperLines = startHelperLines(this.currIframe.root);
        addCleanup(this.helperLines.hide);
        this.draggingHelpers.clone(element); // Clone the dragged element for insertion when dragging a sign field button.
        this.draggingInsideIframe = element.classList.contains(this.signItemSelector); // If the dragged element is a sign item, then it is located inside the iframe

        if (this.draggingInsideIframe) {
            // Save necessary data for repositioning existing sign items.
            const page = element.parentElement;
            element.dataset.pageNumber = page.dataset.pageNumber;
            // Register this cleanup before others so it runs after them (cleanups execute in reverse order).
            // Ensures dragged element positions are refreshed after the framework's cleanup resets them.
            addCleanup(this.currIframe.refreshSignItemPositions.bind(this.currIframe));
        }
    }

    /**
     * Handles setup when dragging starts, including:
     * - Starting scrolling helpers
     * - Cloning and styling the dragged element if needed
     *
     * @param {Object} param0 - Parameters passed by the dragging framework.
     * @returns {void}
     */
    onDragStart({ ctx, addStyle, addClass, removeStyle, addCleanup }) {
        const element = ctx.current.element;
        if (!this.isDraggingActive) {
            return;
        }

        // When dragging a field out of the mobile bottom sheet, collapse the
        // sheet to free the canvas. During the drag the shell must stay mounted
        // (the dragging framework aborts if the dragged element leaves the DOM).
        // Once the drag ends, the sheet state moves to peek, so the dropped
        // field stays visible instead of the sheet springing back over it.
        const mobileShell = element.closest(".o_sign_mobile_shell");
        if (mobileShell) {
            mobileShell.classList.add("o_sign_mobile_shell_force_peek");
            addCleanup(() => {
                this.mobileSheetApi?.collapse();
                mobileShell.classList.remove("o_sign_mobile_shell_force_peek");
            });
        }

        // Edge scrolling is armed only after the pointer first enters the PDF viewer.
        // This prevents unintended scrolling if a drag action starts outside the viewer
        // (which is common on our mobile view).
        this.pointerOffset = { x: 0, y: 0 };
        this.stopScroll = null;
        addCleanup(() => this.stopScroll?.()); // stopScroll is only assigned when the scrolling starts.

        if (this.draggingInsideIframe) {
            // Move the element to be a child of the container instead of the page.
            // This prevents the element from being deleted when dragging across pages,
            // since the iframe uses lazy loading and may remove the original parent page.
            const elementOriginalParent = element.parentElement;
            getIframeViewerContainer(this.currIframe).appendChild(
                elementOriginalParent.removeChild(element)
            );

            // Add cleanup to return the element to its original parent instead of the viewer container when dragging ends
            addCleanup(() => {
                const viewerContainer = getIframeViewerContainer(this.currIframe);
                if (element.parentElement === viewerContainer) {
                    elementOriginalParent.appendChild(viewerContainer.removeChild(element));
                }
            });
        } else {
            this.draggingHelpers.insert(); // Insert a dummy element to maintain the layout while the framework drags the actual element
            addCleanup(this.draggingHelpers.removeClone);
            this.draggingHelpers.style(element, this.currIframe, addStyle, addClass, removeStyle);
        }
    }

    /**
     * Handles the drag logic by:
     * - Positioning the element
     * - Updating scrolling
     * - Drawing helper lines
     *
     * @param {object} param0 - Parameters passed by the dragging framework.
     * @returns {void}
     */
    onDrag({ ctx, addStyle }) {
        const element = ctx.current.element;
        const { x, y } = ctx.pointer;
        if (!this.isDraggingActive) {
            return;
        }

        // overriding the default positioning of the framework as we changes the dimentions of the dragged element based on the pdf dimension
        this.positionElementWithinDraggingContainer(element, x, y, addStyle);

        // update the pointeroffset object to effect the edge scrolling
        const pointerOffset = this.getEdgeScrollOffset(ctx.pointer);
        this.pointerOffset.x = pointerOffset.x;
        this.pointerOffset.y = pointerOffset.y;
        const viewer = getIframeViewerContainer(this.currIframe);
        if (
            !this.stopScroll &&
            pointerOffset.x >= 0 &&
            pointerOffset.y >= 0 &&
            pointerOffset.x <= viewer.clientWidth &&
            pointerOffset.y <= viewer.clientHeight
        ) {
            this.stopScroll = startEdgeScroll(
                viewer,
                this.pointerOffset,
                // Cap the maximum width of the edge scrolling zones on small screens.
                // Otherwise, a relative value like 20% covers too much area on mobile devices,
                // causing auto-scroll to trigger prematurely.
                this.uiService.isSmall ? { maxBoundary: 80 } : undefined
            );
        }

        const elementOffset = this.getElementIframeOffset(element);
        // Draw helper lines if applicable
        if (this.helperLines && elementOffset.x >= 0 && elementOffset.y >= 0) {
            this.helperLines.show(element, { x: elementOffset.x, y: elementOffset.y });
        }
    }

    /**
     * Translates the top-left corner of the given element into coordinates
     * relative to the pdf iframe. An element rect is measured in the
     * viewport of the document owning the element.
     *
     * @param {HTMLElement} element
     * @returns {{x: number, y: number}}
     */
    getElementIframeOffset(element) {
        const rect = element.getBoundingClientRect();
        return this.getIframeOffset({
            x: rect.left,
            y: rect.top,
            view: element.ownerDocument.defaultView,
        });
    }

    /**
     * Handles the drop logic by determining the page where the element was dropped
     * and invoking the dropping function.
     *
     * @param {object} param0 - Parameters passed by the dragging framework.
     * @returns {void}
     */
    onDrop({ ctx }) {
        const element = ctx.current.element;
        if (!this.isDraggingActive) {
            return;
        }

        const pages = this.currIframe.root.querySelectorAll(".page");
        const elementOffset = this.getElementIframeOffset(element);

        for (const page of pages) {
            const pageRect = page.getBoundingClientRect();
            const margin = { left: 0, top: 0, right: 0, bottom: 0 };

            if (
                elementOffset.x >= pageRect.left + margin.left &&
                elementOffset.x <= pageRect.right - margin.right &&
                elementOffset.y >= pageRect.top + margin.top &&
                elementOffset.y <= pageRect.bottom - margin.bottom
            ) {
                const textLayerRect = page.querySelector(".textLayer")?.getBoundingClientRect();
                if (!textLayerRect) {
                    break; // Exit early because the page is not fully loaded yet for dropping.
                }
                this.currIframe.dropSignItem(
                    element,
                    page,
                    elementOffset.x - textLayerRect.left,
                    elementOffset.y - textLayerRect.top
                );
                this.currIframe.markPageForItemPositionRefresh(page); // Save the page to refresh its elements after dragging ends.
                break;
            }
        }
    }

    /**
     * Called when dragging ends.
     *
     * @param {Object} _ - Unused drag end event data.
     * @returns {void}
     */
    onDragEnd() {}

    // ===== End Drag Logic =====

    /**
     * Checks if there are signers without sign items in the template
     * @returns {Boolean}
     */
    get hasSignersWithoutItems() {
        return this.state.signers.some((signer) => signer.itemsCount === 0);
    }

    /**
     * Determines if the "Add Document" button should be displayed in the UI. This serves as an extension point.
     * Other modules can override this to hide the button and prevent document uploads.
     * @returns {Boolean} True if the button should be visible, false otherwise.
     */
    get canAddDocument() {
        return true;
    }

    get signTemplateSidebarProps() {
        const document = this.state.documents.find(
            (doc) => doc.id === this.state.selectedDocumentId
        );
        return {
            iframe: document.iframe,
            signItemTypes: this.signItemTypes,
            isSignRequest: this.resModel === "sign.request",
            updateRoleName: (roleId, roleName) => this.updateRoleName(roleId, roleName),
            deleteRole: (roleId) => this.deleteRole(roleId),
            signTemplateId: this.signTemplate.id,
            signers: this.state.signers,
            hasSignRequests: this.hasSignRequests,
            canAddDocument: this.canAddDocument,
            documents: this.state.documents,
            selectedDocumentId: this.state.selectedDocumentId,
            /* Update callbacks binding for parent. */
            fetchSignItemTypes: () => this.fetchSignItemTypes(),
            onEditTemplate: () => this.onEditTemplate(),
            updateCollapse: (id, value) => this.updateCollapse(id, value),
            updateSigners: this.updateSigners.bind(this),
            pushNewSigner: this.pushNewSigner.bind(this),
            updateDocumentName: (documentId, newName) =>
                this.updateDocumentName(documentId, newName),
            updateSelectedDocument: (id) => this.updateSelectedDocument(id),
            updateDocuments: () => this.updateDocuments(),
            deleteDocument: (documentId) => this.deleteDocument(documentId),
            moveDocumentUp: (documentId) => this.moveDocument(documentId, -1),
            moveDocumentDown: (documentId) => this.moveDocument(documentId, 1),
            moveSignerUp: (signerId) => this.moveSigner(signerId, -1),
            moveSignerDown: (signerId) => this.moveSigner(signerId, 1),
            onUpdateDocument: this.onUpdateDocument.bind(this),
            saveManually: () => this.signStatus.save(),
        };
    }

    get signTemplateMobileShellProps() {
        const signers = this.state.signers;
        const activeSignerId = signers.some((signer) => signer.id === this.state.activeSignerId)
            ? this.state.activeSignerId
            : signers[0]?.id ?? 0;
        return {
            signItemTypes: this.signItemTypes,
            fetchSignItemTypes: () => this.fetchSignItemTypes(),
            signers,
            documents: this.state.documents,
            selectedDocumentId: this.state.selectedDocumentId,
            activeSignerId,
            updateActiveSigner: (id) => {
                this.state.activeSignerId = id;
            },
            updateSelectedDocument: (id) => this.updateSelectedDocument(id),
            updateDocuments: () => this.updateDocuments(),
            pushNewSigner: this.pushNewSigner.bind(this),
            hasSignRequests: this.hasSignRequests,
            canAddDocument: this.canAddDocument,
            signTemplateId: this.signTemplate.id,
            onEditTemplate: () => this.onEditTemplate(),
            registerSheet: (api) => {
                this.mobileSheetApi = api;
            },
            updateRoleName: (roleId, roleName) => this.updateRoleName(roleId, roleName),
            deleteRole: (roleId) => this.deleteRole(roleId),
            updateSigners: this.updateSigners.bind(this),
            moveSignerUp: (signerId) => this.moveSigner(signerId, -1),
            moveSignerDown: (signerId) => this.moveSigner(signerId, 1),
            updateDocumentName: (documentId, newName) =>
                this.updateDocumentName(documentId, newName),
            moveDocumentUp: (documentId) => this.moveDocument(documentId, -1),
            moveDocumentDown: (documentId) => this.moveDocument(documentId, 1),
            deleteDocument: (documentId) => this.deleteDocument(documentId),
            onUpdateDocument: this.onUpdateDocument.bind(this),
            saveManually: () => this.signStatus.save(),
        };
    }

    async onEditTemplate() {
        const duplicatedTemplateIds = await this.orm.call("sign.template", "copy", [
            [this.signTemplate.id],
        ]);
        this.action.doAction({
            type: "ir.actions.client",
            tag: "sign.Template",
            name: this.signTemplate.display_name,
            params: {
                id: duplicatedTemplateIds[0],
            },
        });
    }

    updateRoleName(roleId, roleName) {
        this.orm.write("sign.item.role", [roleId], { name: roleName });
        const signer = this.state.signers.find((s) => s.roleId === roleId);
        if (signer) {
            signer.name = roleName;
        }
        this.state.documents.forEach((document) =>
            document.iframe?.updateRoleName(roleId, roleName)
        );
    }

    deleteRole(roleId) {
        this.state.documents.forEach((document) => document.iframe.deleteRole(roleId));
    }

    waitForIframeToLoad() {
        //TODO: this save methods does n rpc requests, where n is the number of documents.
        //To bo optimized later.
        this.signStatus.save = async () => {
            const saveDocuments = this.state.documents
                .filter((document) => !document.deleted)
                .map((document) => document.iframe?.saveChangesOnBackend());
            // Wait for all save operations to complete
            return Promise.all(saveDocuments);
        };
        let iframesLoaded = false;
        if (this.state.documents) {
            iframesLoaded = true;
            this.state.documents.forEach((document) => {
                if (!document.iframe) {
                    iframesLoaded = false;
                }
            });
        }
        if (iframesLoaded) {
            this.orm
                .call("sign.template", "get_template_items_roles_info", [this.templateID])
                .then((info) => {
                    /* Make all signers collapsed when loading for the first time. */
                    const updatedInfo = info.map((item) => ({
                        ...item,
                        isCollapsed: true,
                        isInputFocused: false,
                        itemsCount: 0,
                    }));

                    /* Make the last signer uncollapsed. */
                    if (updatedInfo.length > 0) {
                        updatedInfo[updatedInfo.length - 1].isCollapsed = false;
                    }

                    /* Update signer's loaded information. */
                    this.updateSigners(updatedInfo);
                    this.state.nextId = this.state.signers.length;

                    /* We must have at least one signer after load, unless the template has sign requests. */
                    if (updatedInfo.length == 0 && !this.hasSignRequests) {
                        this.pushNewSigner();
                    }

                    /* Set callback for tracking number of items of each signer and load font. */
                    this.state.documents.forEach((document) => {
                        document.iframe.setFont(this.font);
                    });
                });
        } else {
            setTimeout(() => this.waitForIframeToLoad(), 50);
        }
    }

    updateSigners(newSigners) {
        this.state.signers = newSigners;
        this.state.signers.forEach((signer) => {
            this.state.documents.forEach((document) => {
                document.iframe.setRoleColor(signer.roleId, signer.colorId);
            });
        });
    }

    updateSignItemsCount() {
        const updatedSigners = this.state.signers;
        updatedSigners.forEach((signer) => {
            signer.itemsCount = 0;
            this.state.documents.forEach((document) => {
                if (document.iframe.signItemsCountByRole) {
                    signer.itemsCount += document.iframe.signItemsCountByRole[signer.roleId] || 0;
                }
            });
        });
        this.updateSigners(updatedSigners);
    }

    async pushNewSigner() {
        const name = _t("Signer ") + (this.state.nextId + 1).toString();
        const roleId = await this.orm.call("sign.template", "create_item_and_role", [
            this.state.selectedDocumentId,
            name,
        ]);
        const colorId = this.getNextColor();
        this.state.signers.push({
            id: this.state.nextId,
            name: name,
            roleId: roleId,
            colorId: colorId,
            isCollapsed: false,
            itemsCount: 0,
            isInputFocused: true,
        });
        this.updateCollapse(this.state.nextId, false);
        this.state.documents.forEach((document) => {
            document.iframe.setRoleColor(roleId, colorId);
        });
        this.state.nextId++;
    }

    updateCollapse(id, value) {
        /* Make the signer with the matching id receive the new value,
        and force all other signers to have its dropdown collapsed. */
        this.state.signers.forEach((signer) => {
            if (signer.id === id) {
                signer.isCollapsed = value;
            } else {
                signer.isCollapsed = true;
                signer.isInputFocused = false;
            }
        });
    }

    getNextColor() {
        const colors = this.state.signers.map((signer) => signer.colorId);
        for (let i = 0; i < 55; i++) {
            if (!colors.includes(i)) {
                return i;
            }
        }
        return 0;
    }

    async updateDocuments() {
        const documents = await this.orm.call("sign.document", "search_read", [
            [["template_id", "=", this.templateID]],
        ]);
        const new_documents = documents.filter(
            (document) => !this.state.documentIds.includes(document.id)
        );
        new_documents.forEach((document) => {
            this.state.documentIds.push(document.id);
            document.attachment_location = `/web/content/${document.attachment_id[0]}`;
            document.iframe = undefined;
            document.setIframe = (iframe) => {
                document.iframe = iframe;
                if (!document.iframe) {
                    return;
                }
                document.iframe.setFont(this.font);
                this.state.signers.forEach((signer) => {
                    document.iframe.setRoleColor(signer.roleId, signer.colorId);
                });
                this.signStatus.save = async () => {
                    const saveDocuments = this.state.documents
                        .filter((document) => !document.deleted)
                        .map((document) => document.iframe?.saveChangesOnBackend());
                    // Wait for all save operations to complete
                    return Promise.all(saveDocuments);
                };
            };
            this.state.documents.push(document);
        });
    }

    _getTemplateFields() {
        return [
            "id",
            "name",
            "has_sign_requests",
            "signed_count",
            "responsible_count",
            "display_name",
            "active",
            "model_name",
            "user_id",
        ];
    }

    async fetchTemplateData() {
        const template = await this.orm.call("sign.template", "read", [
            [this.templateID],
            this._getTemplateFields(),
        ]);

        if (!template.length) {
            this.templateID = undefined;
            this.notification.add(_t("The template doesn't exist anymore."), {
                type: "warning",
            });
            return;
        }
        this.state.documents = await this.orm.call("sign.document", "search_read", [
            [["template_id", "=", this.templateID]],
        ]);
        this.state.documentIds = this.state.documents.map((document) => document.id);
        this.state.selectedDocumentId = this.state.documentIds[0];
        this.state.documents.forEach((document) => {
            document.attachment_location = `/web/content/${document.attachment_id[0]}`;
            document.iframe = undefined;
            document.setIframe = (iframe) => {
                document.iframe = iframe;
            };
        });
        this.signTemplate = template[0];
        this.hasSignRequests = this.signTemplate.has_sign_requests;
        this.responsibleCount = this.signTemplate.responsible_count;
        this.manageTemplateAccess = await this.checkManageTemplateAccess();

        return Promise.all([this.fetchSignItemData(), this.fetchSignItemTypes()]);
    }

    async fetchFont() {
        const fonts = await rpc("/web/sign/get_fonts/LaBelleAurore-Regular.ttf");
        this.font = fonts[0];
    }

    async fetchSignItemTypes() {
        let domain = [];
        let modelName = this.signTemplate.model_name;
        if (this.referenceDoc && !modelName) {
            modelName = this.referenceDoc.split(",")[0];
        }
        if (modelName) {
            domain = [
                "|",
                ["model_name", "=", false],
                ["model_name", "in", [modelName, "res.partner"]],
            ];
        }
        this.signItemTypes = await this.orm.call(
            "sign.item.type",
            "get_sidebar_item_types",
            [this.signTemplate.id, domain],
            {
                context: {
                    ...user.context,
                },
            }
        );
        return this.signItemTypes;
    }

    async fetchSignItemData() {
        this.signItemOptions = await this.orm.call(
            "sign.item.option",
            "search_read",
            [[], ["id", "value"]],
            { context: user.context }
        );
    }

    /**
     * True if the user can manage who has access to this template: must be the
     * owner or a Sign Administrator, and must also have manage_template_access.
     */
    async checkManageTemplateAccess() {
        const isOwner = this.signTemplate.user_id && this.signTemplate.user_id[0] === user.userId;
        return (
            ((await user.hasGroup("sign.group_sign_manager")) || isOwner) &&
            (await user.hasGroup("sign.manage_template_access"))
        );
    }

    goBackToKanban() {
        return this.action.doAction("sign.sign_template_action", { clearBreadcrumbs: true });
    }

    /**
     * Discards unsaved sign-item edits in place for all active documents. Keeps the current action and PDF
     * iframes mounted, fetch the items info from the back-end and assign them to the front-end to replace drafts visually.
     */
    async discardChanges() {
        this.signStatus.isTemplateChanged = false;
        this.signStatus.isDiscardingChanges = true;
        try {
            const activeDocuments = this.state.documents.filter((document) => !document.deleted);
            for (const document of activeDocuments) {
                const [radioSets, signItems] = await Promise.all([
                    this.orm.call("sign.document", "get_radio_sets_dict", [document.id]),
                    this.orm.call(
                        "sign.item",
                        "search_read",
                        [[["document_id", "=", document.id]]],
                        { context: user.context }
                    ),
                ]);
                signItems.forEach((item) => {
                    item.type_id = item.type_id[0];
                    item.radio_set_id = item.radio_set_id[0];
                    item.roleName = item.responsible_id[1];
                    item.document_id = item.document_id[0];
                });
                document.iframe?.discardUnsavedChanges(signItems, radioSets);
            }
            this.updateSignItemsCount();
        } finally {
            this.signStatus.isDiscardingChanges = false;
        }
    }

    async onTemplateSaveClick() {
        const templateId = this.signTemplate.id;
        this.state.properties = await this.orm.call("sign.template", "write", [
            [templateId],
            { active: true, is_one_time_request: false },
        ]);
        this.signTemplate.active = true;
        this.notification.add(_t("Document saved as Template."), { type: "success" });
        return this.state.properties;
    }

    getSignTemplateBodyProps(documentId) {
        const document = this.state.documents.find((doc) => doc.id === documentId);
        return {
            attachmentLocation: document.attachment_location,
            manageTemplateAccess: this.manageTemplateAccess,
            hasSignRequests: this.hasSignRequests,
            signTemplate: this.signTemplate,
            signItemTypes: this.signItemTypes,
            signItems: this.signItems,
            radioSets: this.radioSets,
            signItemOptions: this.signItemOptions,
            goBackToKanban: () => this.goBackToKanban(),
            resModel: this.resModel,
            signStatus: this.signStatus,
            iframe: document.iframe,
            setIframe: (iframe) => {
                document.setIframe(iframe);
                this.bodyIframes[documentId] = iframe;
            },
            onTemplateSaveClick: () => this.onTemplateSaveClick(),
            documentId: documentId,
            updateSignItemsCountCallback: () => this.updateSignItemsCount(),
        };
    }

    updateSelectedDocument(documentId) {
        this.state.selectedDocumentId = documentId;
    }

    async updateDocumentName(documentId, newName) {
        const document = this.state.documents.find((doc) => doc.id === documentId);
        if (document && newName !== document.display_name) {
            document.display_name = newName;
            await this.orm.write("sign.document", [documentId], { name: newName });
        }
    }

    async deleteDocument(documentId) {
        if (this.state.documents.length === 1) {
            return;
        }
        if (this.state.selectedDocumentId === documentId) {
            this.updateSelectedDocument(this.getNewFocusedDocument(documentId).id);
        }
        const document = this.state.documents.find((doc) => doc.id === documentId);
        document.deleted = true;
        await this.orm.unlink("sign.document", [documentId]);
    }

    /**
     *
     * @param {Number} documentId
     * @param {Number} direction
     * Moves the document up (direction = -1) or down (direction = 1) in the list of documents,
     * by swapping the sequence numbers of the two documents.
     */
    async moveDocument(documentId, direction) {
        const active_documents = this.state.documents
            .filter((doc) => !doc.deleted)
            .sort((a, b) => a.sequence - b.sequence);
        const index_1 = active_documents.findIndex((doc) => doc.id === documentId);
        const index_2 = index_1 + direction;
        if (index_2 < 0 || index_2 >= active_documents.length) {
            return;
        }
        const document_a = active_documents[index_1];
        const document_b = active_documents[index_2];
        const seq_a = document_a.sequence;
        const seq_b = document_b.sequence;
        document_a.sequence = seq_b;
        document_b.sequence = seq_a;
        await this.orm.write("sign.document", [document_a.id], { sequence: seq_b });
        await this.orm.write("sign.document", [document_b.id], { sequence: seq_a });

        // update template name based on current first doc
        if (index_1 === 0 || index_2 === 0) {
            const oldFirstDocument = active_documents[0];
            const newFirstDocument = index_1 === 0 ? document_b : document_a;
            // Logic: Only update the template name if it matches the *old* first document's name.
            // This implies the user hasn't set a custom name manually. If the names don't match
            //we assume it's a custom name and leave it alone.
            if (
                newFirstDocument.id !== oldFirstDocument.id &&
                this.signTemplate.name === oldFirstDocument.name
            ) {
                this.signTemplate.name = newFirstDocument.name;
                this.signTemplate.display_name = newFirstDocument.name;
                await this.orm.write("sign.template", [this.signTemplate.id], {
                    name: newFirstDocument.name,
                });
                this.env.config.setDisplayName(this.signTemplate.display_name);
            }
        }
    }

    getNewFocusedDocument(oldFocusedDocumentId) {
        return this.state.documents.find((doc) => doc.id !== oldFocusedDocumentId && !doc.deleted);
    }

    /**
     *
     * @param {Number} signerId
     * @param {Number} direction
     * Moves the signer up (direction = -1) or down (direction = 1) in the list of signers,
     * by swapping the entry positions and persisting new sequence values on sign.item.role.
     */
    async moveSigner(signerId, direction) {
        const signers = [...this.state.signers];
        const index_1 = signers.findIndex((signer) => signer.id === signerId);
        const index_2 = index_1 + direction;
        if (index_1 < 0 || index_2 < 0 || index_2 >= signers.length) {
            return;
        }
        [signers[index_1], signers[index_2]] = [signers[index_2], signers[index_1]];
        this.state.signers = signers;
        await Promise.all(
            signers.map((signer, idx) =>
                this.orm.write("sign.item.role", [signer.roleId], { sequence: idx + 1 })
            )
        );
    }

    async showConfirmationDialog() {
        return new Promise((resolve) => {
            this.dialog.add(ConfirmationDialog, {
                title: _t("Confirmation"),
                body: _t(
                    "Your changes will be discarded. Would you like to save them as a template?"
                ),
                confirm: async () => {
                    await this.onTemplateSaveClick();
                    if (this.signStatus.isTemplateChanged) {
                        // If there is unsaved sign items, it will save the template before leaving.
                        await this.signStatus.save();
                    }
                    resolve(true);
                },
                confirmLabel: _t("Save & close"),
                cancel: () => {
                    resolve(true);
                },
                dismiss: () => {
                    resolve(false);
                },
            });
        });
    }

    async onUpdateDocument(documentId, file) {
        /* Update document by duplicating and archiving the current template. */
        new Promise((resolve) => {
            this.dialog.add(ConfirmationDialog, {
                title: _t("Replace Document"),
                body: _t(
                    "Updating a document will copy the items, and they will " +
                        "land at the same coordinates as the original ones if the " +
                        "number of pages match with the previous PDF. Do you want to proceed?"
                ),
                confirmLabel: _t("Replace Document"),
                confirm: () => resolve(true),
                cancel: () => resolve(false),
                dismiss: () => resolve(false),
            });
        }).then(async (confirmed) => {
            if (!confirmed) {
                return;
            }
            const action = await this.orm.call("sign.template", "update_document", [
                [this.signTemplate.id],
                documentId,
                file,
            ]);
            this.action.doAction(action, { clearBreadcrumbs: true });
        });
    }
}

registry.category("actions").add("sign.Template", SignTemplate);
