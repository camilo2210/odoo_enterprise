import { Component, proxy, signal, t, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { clamp } from "@web/core/utils/numbers";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { useBackButton } from "@web/core/utils/hooks";
import { getViewportDimensions, useViewportChange } from "@web/core/utils/dvu";
import { SignTemplateMobileFieldsPanel } from "./sign_template_mobile_fields_panel";
import { SignTemplateMobileSignersPanel } from "./sign_template_mobile_signers_panel";
import { SignTemplateMobileDocumentsPanel } from "./sign_template_mobile_documents_panel";

// The sheet is the persistent bottom panel that hosts the active tab's panel.
// It rests at one of three "snaps": the user drags the handle to
// resize it freely and, on release, it settles onto one of these heights.
//   peek – only the handle + tab bar are visible, panel content is hidden
//   half – ~50% of the editor height
//   full – ~90% of the editor height
// SNAP_ORDER lists them by ascending height. chooseSnap() relies on that order
// to walk to the next snap in a flick's direction.
const SNAP_ORDER = ["peek", "half", "full"];
// A flick is a fast handle release. Above this pointer speed (px/ms) the sheet
// jumps one snap in the gesture's direction instead of settling to the
// nearest one.
const FLICK_VELOCITY = 0.4;
const EDITABLE_SELECTOR = "input, textarea, select, [contenteditable='true']";

/**
 * Bottom shell of the mobile template editor: a tab bar (Fields | Signers |
 * Documents) sitting over a resizable sheet that hosts the active tab's panel.
 * Owns the sheet's snap state and handle gesture, and keeps an edited input
 * scrolled above the on-screen keyboard. The actual editor state (signers,
 * documents, sign items) lives on the shared SignTemplate root and is threaded
 * in through props.
 */
export class SignTemplateMobileShell extends Component {
    static template = "sign.SignTemplateMobileShell";
    static components = {
        SignTemplateMobileFieldsPanel,
        SignTemplateMobileSignersPanel,
        SignTemplateMobileDocumentsPanel,
    };

    props = useProps({
        signItemTypes: t.array(),
        fetchSignItemTypes: t.function(),
        signers: t.array(),
        documents: t.array(),
        selectedDocumentId: t.number(),
        activeSignerId: t.number(),
        updateActiveSigner: t.function(),
        updateSelectedDocument: t.function(),
        updateDocuments: t.function(),
        pushNewSigner: t.function(),
        hasSignRequests: t.boolean(),
        canAddDocument: t.boolean().optional(),
        signTemplateId: t.number(),
        onEditTemplate: t.function(),
        registerSheet: t.function(),
        updateRoleName: t.function(),
        deleteRole: t.function(),
        updateSigners: t.function(),
        moveSignerUp: t.function(),
        moveSignerDown: t.function(),
        updateDocumentName: t.function(),
        moveDocumentUp: t.function(),
        moveDocumentDown: t.function(),
        deleteDocument: t.function(),
        onUpdateDocument: t.function(),
        saveManually: t.function(),
    });

    rootRef = signal.ref();
    contentRef = signal.ref();

    setup() {
        this.state = proxy({
            activeTab: "fields",
            snap: "peek",
        });
        // Hand the root a way to drop the sheet back to peek, e.g. once it has
        // finished handing a dragged field off to the document.
        this.props.registerSheet({
            collapse: () => this.collapse(),
        });
        this.keyboardState = { active: false };
        // The visual viewport shrinks when the on-screen keyboard opens/closes;
        // re-measure the overlap so the focused input stays visible above it.
        useViewportChange(() => this.updateKeyboardOffset());
        this.tabs = [
            { id: "fields", label: _t("Fields"), icon: "add_box" },
            { id: "signers", label: _t("Signers"), icon: "group" },
            { id: "documents", label: _t("Documents"), icon: "description" },
        ];
        useHotkey("escape", () => this.collapse(), {
            isAvailable: () => this.state.snap !== "peek",
        });
        // Hardware back button (mobile app): collapse instead of navigating.
        useBackButton(
            () => this.collapse(),
            () => this.state.snap !== "peek"
        );
    }

    get activeSigner() {
        return this.props.signers.find((signer) => signer.id === this.props.activeSignerId);
    }

    get selectedDocument() {
        return this.props.documents.find((doc) => doc.id === this.props.selectedDocumentId);
    }

    get fieldsPanelProps() {
        return {
            signItemTypes: this.props.signItemTypes,
            signer: this.activeSigner,
            documentName: this.selectedDocument?.display_name || "",
            hasSignRequests: this.props.hasSignRequests,
            iframe: this.selectedDocument?.iframe,
            fetchSignItemTypes: this.props.fetchSignItemTypes,
        };
    }

    get signersPanelProps() {
        return {
            signers: this.props.signers,
            activeSignerId: this.props.activeSignerId,
            updateActiveSigner: this.props.updateActiveSigner,
            pushNewSigner: this.props.pushNewSigner,
            hasSignRequests: this.props.hasSignRequests,
            signTemplateId: this.props.signTemplateId,
            updateRoleName: this.props.updateRoleName,
            deleteRole: this.props.deleteRole,
            updateSigners: this.props.updateSigners,
            moveSignerUp: this.props.moveSignerUp,
            moveSignerDown: this.props.moveSignerDown,
        };
    }

    get documentsPanelProps() {
        return {
            documents: this.props.documents,
            selectedDocumentId: this.props.selectedDocumentId,
            updateSelectedDocument: this.props.updateSelectedDocument,
            updateDocuments: this.props.updateDocuments,
            signTemplateId: this.props.signTemplateId,
            hasSignRequests: this.props.hasSignRequests,
            canAddDocument: this.props.canAddDocument,
            updateDocumentName: this.props.updateDocumentName,
            moveDocumentUp: this.props.moveDocumentUp,
            moveDocumentDown: this.props.moveDocumentDown,
            deleteDocument: this.props.deleteDocument,
            onUpdateDocument: this.props.onUpdateDocument,
            saveManually: this.props.saveManually,
        };
    }

    collapse() {
        this.state.snap = "peek";
    }

    /**
     * While an input inside the sheet is being edited, the sheet expands to
     * full and the content gets bottom padding matching the on-screen
     * keyboard overlap, so the input can always be scrolled above the
     * keyboard. The previous snap state is restored on blur.
     */
    onContentFocusIn(ev) {
        if (!ev.target.matches(EDITABLE_SELECTOR)) {
            return;
        }
        if (!this.keyboardState.active) {
            this.keyboardState = { active: true, previousSnap: this.state.snap };
            this.state.snap = "full";
        }
        this.keyboardState.target = ev.target;
        this.updateKeyboardOffset();
    }

    onContentFocusOut(ev) {
        if (!this.keyboardState.active) {
            return;
        }
        // Focus moving to another input of the sheet keeps the keyboard open.
        if (
            ev.relatedTarget &&
            this.contentRef().contains(ev.relatedTarget) &&
            ev.relatedTarget.matches(EDITABLE_SELECTOR)
        ) {
            return;
        }
        this.state.snap = this.keyboardState.previousSnap;
        this.keyboardState = { active: false };
        this.contentRef().style.removeProperty("padding-bottom");
    }

    updateKeyboardOffset() {
        if (!this.keyboardState.active) {
            return;
        }
        // How much of the layout viewport the keyboard covers = the gap between
        // the full window height and the (shrunk) visual viewport height.
        const overlap = Math.max(0, window.innerHeight - getViewportDimensions().height);
        this.contentRef().style.paddingBottom = overlap ? `${overlap}px` : "";
        // Wait for the padding to apply before scrolling the input into view.
        requestAnimationFrame(() => {
            this.keyboardState.target?.scrollIntoView({ block: "nearest" });
        });
    }

    onTabClick(tabId) {
        this.state.activeTab = tabId;
        // Picking a tab from peek raises the sheet so its panel is actually visible.
        if (this.state.snap === "peek") {
            this.state.snap = "half";
        }
    }

    // Snap heights in pixels, measured dynamically as they depend on the current handle
    // and tab-bar sizes and on the editor's height, which vary across devices.
    getSnapHeights() {
        const shell = this.rootRef();
        const handleHeight = shell.querySelector(".o_sign_mobile_sheet_handle").offsetHeight;
        const tabbarHeight = shell.querySelector(".o_sign_mobile_tabbar").offsetHeight;
        const containerHeight = shell.parentElement.clientHeight;
        return {
            peek: handleHeight + tabbarHeight,
            half: containerHeight * 0.5,
            full: containerHeight * 0.9,
        };
    }

    /**
     * Resolve the snap the sheet should rest on after a resize. A flick jumps
     * one snap in its direction, a slower release settles to the nearest one.
     */
    chooseSnap(height, velocity, heights) {
        // Fast flick: jump to the first snap past the current height in the
        // flick's direction, regardless of which snap is nearest.
        if (Math.abs(velocity) > FLICK_VELOCITY) {
            // clientY grows downward: a negative velocity is an upward flick.
            const goingUp = velocity < 0;
            const candidates = SNAP_ORDER.filter((snap) =>
                goingUp ? heights[snap] > height : heights[snap] < height
            );
            if (candidates.length) {
                return goingUp ? candidates[0] : candidates[candidates.length - 1];
            }
        }
        // Slow release: settle on the snap closest to the current sheet height.
        return SNAP_ORDER.reduce((best, snap) =>
            Math.abs(heights[snap] - height) < Math.abs(heights[best] - height) ? snap : best
        );
    }

    /**
     * Starts a resize interaction. The caller feeds pointer positions through
     * move() and finishes with end() (snaps) or cancel().
     */
    startResizeSession(startY) {
        const shell = this.rootRef();
        const heights = this.getSnapHeights();
        const startHeight = shell.offsetHeight;
        let currentHeight = startHeight;
        let lastY = null;
        let lastT = null;
        let velocity = 0;
        shell.classList.add("o_sign_mobile_shell_resizing");
        const cleanup = () => {
            shell.classList.remove("o_sign_mobile_shell_resizing");
            shell.style.height = "";
        };
        return {
            move: (clientY, timeStamp) => {
                // Track the latest pointer velocity so end() can detect a flick.
                if (lastY !== null && timeStamp > lastT) {
                    velocity = (clientY - lastY) / (timeStamp - lastT);
                }
                lastY = clientY;
                lastT = timeStamp;
                currentHeight = clamp(startHeight + (startY - clientY), heights.peek, heights.full);
                shell.style.height = `${currentHeight}px`;
            },
            end: () => {
                cleanup();
                this.state.snap = this.chooseSnap(currentHeight, velocity, heights);
            },
            cancel: cleanup,
        };
    }

    /**
     * Drag the handle to resize the sheet, release snaps to a snap point.
     * A simple tap toggles between peek and the half state.
     */
    onHandlePointerDown(ev) {
        const handle = ev.currentTarget;
        const startY = ev.clientY;
        let session = null;
        try {
            handle.setPointerCapture(ev.pointerId);
        } catch {
            // The pointer may already be released (fast tap). The tap logic
            // in onPointerUp still applies without capture.
        }
        const onPointerMove = (e) => {
            // Only promote to a resize once the pointer travels past a small
            // threshold, so a jittery tap is not mistaken for a drag.
            if (!session && Math.abs(e.clientY - startY) > 5) {
                session = this.startResizeSession(startY);
            }
            session?.move(e.clientY, e.timeStamp);
        };
        const onPointerUp = () => {
            handle.removeEventListener("pointermove", onPointerMove);
            handle.removeEventListener("pointerup", onPointerUp);
            handle.removeEventListener("pointercancel", onPointerUp);
            if (session) {
                session.end();
            } else {
                this.state.snap = this.state.snap === "peek" ? "half" : "peek"; // simple tap
            }
        };
        handle.addEventListener("pointermove", onPointerMove);
        handle.addEventListener("pointerup", onPointerUp);
        handle.addEventListener("pointercancel", onPointerUp);
    }
}
