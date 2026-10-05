import { Plugin } from "@html_editor/plugin";
import { getActiveHotkey } from "@web/core/hotkeys/hotkey_utils";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { uuid } from "@web/core/utils/strings";
import { aiChannelBus } from "@ai/utils/ai_channel_bus";
import {
    AI_EDITABLE_ZONE_SELECTORS,
    AI_WEBSITE_ELEMENT_SELECTION_COMMAND,
    AI_WEBSITE_ELEMENT_SELECTION_STATE,
    isAiWebsiteBuilderChannel,
} from "@ai_website/utils";

export class AiWebsiteElementSelectionPlugin extends Plugin {
    static id = "aiWebsiteElementSelection";
    static dependencies = ["aiWebsiteBuilder", "builderOptions", "localOverlay"];

    // Resources are available before setup, including during the base plugin's setup.
    selections = new Map();
    hoverOverlay = null;
    pickerActive = false;

    resources = {
        system_attributes: ["data-ai-id"],
        clean_for_save_processors: this.cleanEditorMarkers.bind(this),
        on_layout_geometry_change_handlers: this.refreshSelectionOverlays.bind(this),
        on_committed_to_history_handlers: this.reconcileSelection.bind(this),
        on_ai_website_page_context_handlers: () => {
            const selectedElements = this.consumeSelectedElementsContext();
            return selectedElements.length ? { selected_elements: selectedElements } : {};
        },
        on_ai_website_html_imported_handlers: this.cleanEditorMarkers.bind(this),
        on_ai_website_element_replaced_handlers: (oldElement, newElement) => {
            if (oldElement.dataset.aiId) {
                newElement.dataset.aiId = oldElement.dataset.aiId;
            }
        },
    };

    setup() {
        this.dependencies.aiWebsiteBuilder.registerClientToolWithMutex(
            "fetch_website_styles",
            (params) => this.getElementStyles(params)
        );
        this.pickerOverlayContainer = this.config.localOverlayContainers?.ref();
        this.selectionOverlayContainer = this.dependencies.localOverlay.makeLocalOverlay(
            "ai-website-selection-overlay-container"
        );
        this.document.body.append(this.selectionOverlayContainer);
        this.onSelectionCommand = this.onSelectionCommand.bind(this);
        aiChannelBus.addEventListener(
            AI_WEBSITE_ELEMENT_SELECTION_COMMAND,
            this.onSelectionCommand
        );
        for (const eventName of ["pointerdown", "pointerup", "click", "dblclick"]) {
            this.addGlobalDomListener(eventName, this.onPickerEvent, true);
        }
        this.addDomListener(window, "keydown", this.onPickerEscape, true, true);
        if (this.window !== window) {
            this.addDomListener(this.window, "keydown", this.onPickerEscape, true, true);
        }
        this.addDomListener(this.editable, "mousemove", this.onPickerHover);
        this.addDomListener(this.editable, "mouseleave", () => this.setHoveredTarget(null));
        this.addDomListener(this.document, "scroll", this.refreshSelectionOverlays, true);
        this.emitSelectionState();
    }

    destroy() {
        aiChannelBus.removeEventListener(
            AI_WEBSITE_ELEMENT_SELECTION_COMMAND,
            this.onSelectionCommand
        );
        this.setPickerActive(false);
        this.cleanEditorMarkers(this.editable);
        aiChannelBus.trigger(AI_WEBSITE_ELEMENT_SELECTION_STATE, {
            available: false,
            pickerActive: false,
            elements: [],
        });

        super.destroy();
    }

    onSelectionCommand({ detail: command }) {
        switch (command.type) {
            case "request_state":
                break;
            case "toggle_picker":
                this.setPickerActive(!this.pickerActive);
                if (this.pickerActive) {
                    this.dependencies.builderOptions.deactivateContainers();
                }
                break;
            case "deselect":
                this.removeSelection(command.id);
                break;
            case "stop_picker":
                this.setPickerActive(false);
                break;
            case "release":
                this.setPickerActive(false);
                this.selections.forEach(({ overlay }) => overlay.remove());
                this.selections.clear();
                break;
            case "prepare_send":
                command.elementLabels = this.getSelectionState().elements.map(({ label }) => label);
                this.setPickerActive(false);
                break;
            default:
                return;
        }
        this.emitSelectionState();
    }

    emitSelectionState() {
        aiChannelBus.trigger(AI_WEBSITE_ELEMENT_SELECTION_STATE, this.getSelectionState());
    }

    getElementStyles({ elements }) {
        return {
            elements: elements.map(({ id, properties }) => {
                const target = this.editable.querySelector(`[data-ai-id="${id}"]`);
                if (!target) {
                    return { id, error: "Element is no longer available" };
                }
                const computedStyle = this.window.getComputedStyle(target);
                return {
                    id,
                    styles: Object.fromEntries(
                        properties.map((property) => [
                            property,
                            computedStyle.getPropertyValue(property),
                        ])
                    ),
                };
            }),
        };
    }

    onPickerEvent(event) {
        if (!this.pickerActive || event.button !== 0) {
            return;
        }
        event.preventDefault();
        event.stopImmediatePropagation();
        if (event.type === "click" && event.detail <= 1) {
            this.selectElement(event.target);
        }
    }

    onPickerEscape(event) {
        if (!this.pickerActive || getActiveHotkey(event) !== "escape") {
            return;
        }
        event.preventDefault();
        event.stopImmediatePropagation();
        this.setPickerActive(false);
        this.emitSelectionState();
        [...this.services["mail.store"].chatHub.opened]
            .find((chatWindow) => isAiWebsiteBuilderChannel(chatWindow.channel))
            ?.focus();
    }

    onPickerHover(event) {
        if (!this.pickerActive) {
            return;
        }
        const target = this.dependencies.builderOptions.closestWithOption(event.target);
        this.setHoveredTarget(target && this.isInsideEditableZone(target) ? target : null);
    }

    createOverlay(target) {
        const overlay = this.selectionOverlayContainer.ownerDocument.createElement("div");
        const entry = { target, overlay };
        overlay.className = "o-ai-website-selection-overlay";
        this.selectionOverlayContainer.append(overlay);
        this.refreshSelectionOverlay(entry);
        return entry;
    }

    refreshSelectionOverlay({ target, overlay }) {
        if (!target.isConnected) {
            return;
        }
        const style = this.window.getComputedStyle(target);
        const targetRect = target.getBoundingClientRect();
        const overlayContainerRect = this.selectionOverlayContainer.getBoundingClientRect();
        const fixedTop = Math.max(
            0,
            ...[...this.document.querySelectorAll(".o_top_fixed_element")].map(
                (element) => element.getBoundingClientRect().bottom
            )
        );
        const clippedTop = Math.min(targetRect.height, Math.max(0, fixedTop - targetRect.top));
        Object.assign(overlay.style, {
            position: "absolute",
            boxSizing: "border-box",
            border: "2px solid #00d9ff",
            background: "rgba(0, 217, 255, 0.12)",
            width: `${targetRect.width}px`,
            height: `${targetRect.height}px`,
            top: `${targetRect.top - overlayContainerRect.top}px`,
            left: `${targetRect.left - overlayContainerRect.left}px`,
            clipPath: clippedTop ? `inset(${clippedTop}px 0 0)` : "",
            borderRadius: style.borderRadius,
        });
    }

    refreshSelectionOverlays() {
        if (this.hoverOverlay) {
            if (this.hoverOverlay.target.isConnected) {
                this.refreshSelectionOverlay(this.hoverOverlay);
            } else {
                this.setHoveredTarget(null);
            }
        }
        for (const entry of this.selections.values()) {
            this.refreshSelectionOverlay(entry);
        }
    }

    setHoveredTarget(target) {
        if (this.hoverOverlay?.target === target) {
            return;
        }
        this.hoverOverlay?.overlay.remove();
        const isSelected = this.selections.has(target?.dataset.aiId);
        this.hoverOverlay = target && !isSelected ? this.createOverlay(target) : null;
    }

    setPickerActive(active) {
        this.pickerActive = active;
        this.document.documentElement.classList.toggle("o-ai-website-picker-active", active);
        this.pickerOverlayContainer?.classList.toggle("o-ai-website-picker-active", active);
        if (!active) {
            this.setHoveredTarget(null);
        }
    }

    isInsideEditableZone(target) {
        for (const selector of Object.values(AI_EDITABLE_ZONE_SELECTORS)) {
            const zone = this.editable.querySelector(selector);
            if (zone && zone !== target && zone.contains(target)) {
                return true;
            }
        }
        return false;
    }

    selectElement(rawTarget) {
        const target = this.dependencies.builderOptions.closestWithOption(rawTarget);
        if (!target || !this.isInsideEditableZone(target)) {
            this.services.notification.add(
                _t("This area cannot be targeted. Select a website building block instead."),
                { type: "warning" }
            );
            return;
        }
        const id = target.dataset.aiId || `ai-${uuid()}`;
        if (this.selections.has(id)) {
            this.removeSelection(id);
            this.emitSelectionState();
            return;
        }

        for (const [selectedId, { target: selectedTarget }] of this.selections) {
            if (selectedTarget.contains(target) || target.contains(selectedTarget)) {
                this.removeSelection(selectedId);
            }
        }
        target.dataset.aiId = id;
        this.setHoveredTarget(null);
        this.selections.set(id, this.createOverlay(target));
        this.emitSelectionState();
    }

    removeSelection(id) {
        const selection = this.selections.get(id);
        selection.overlay.remove();
        this.selections.delete(id);
    }

    reconcileSelection() {
        const hadSelections = Boolean(this.selections.size);
        for (const [id, selection] of this.selections) {
            const { target } = selection;
            if (!this.isInsideEditableZone(target) || target.dataset.aiId !== id) {
                this.removeSelection(id);
            } else {
                this.refreshSelectionOverlay(selection);
            }
        }
        if (hadSelections) {
            this.emitSelectionState();
        }
    }

    getSelectionState() {
        return {
            available: true,
            pickerActive: this.pickerActive,
            elements: [...this.selections].map(([id, { target }]) => {
                const tag = target.tagName.toLowerCase();
                // First line with a letter/number, skipping icon/emoji-only lines.
                const firstReadableLine = target.innerText
                    .trim()
                    .split("\n")
                    .map((line) => line.trim())
                    .find((line) => /[\p{L}\p{N}]/u.test(line));
                return {
                    id,
                    label: firstReadableLine?.slice(0, 60) || `<${tag}>`,
                };
            }),
        };
    }

    consumeSelectedElementsContext() {
        const context = [...this.selections].map(([id, { target }]) => {
            const style = this.window.getComputedStyle(target);
            const rect = target.getBoundingClientRect();
            return {
                id,
                tag: target.tagName.toLowerCase(),
                text: target.innerText.replace(/\s+/g, " ").trim().slice(0, 200),
                size: {
                    width: Math.round(rect.width),
                    height: Math.round(rect.height),
                },
                computed_style: {
                    display: style.display,
                    position: style.position,
                    margin: style.margin,
                    padding: style.padding,
                    color: style.color,
                    font: style.font,
                    "text-align": style.textAlign,
                    "background-color": style.backgroundColor,
                    border: style.border,
                    "border-radius": style.borderRadius,
                    "flex-flow": style.flexFlow,
                    "justify-content": style.justifyContent,
                    "align-items": style.alignItems,
                    gap: style.gap,
                    "grid-template-columns": style.gridTemplateColumns,
                    "object-fit": style.objectFit,
                    "object-position": style.objectPosition,
                    "aspect-ratio": style.aspectRatio,
                },
            };
        });
        this.selections.forEach(({ overlay }) => overlay.remove());
        this.selections.clear();
        this.emitSelectionState();
        return context;
    }

    cleanEditorMarkers(root) {
        root.removeAttribute("data-ai-id");
        root.querySelectorAll("[data-ai-id]").forEach((el) => {
            el.removeAttribute("data-ai-id");
        });
        return root;
    }
}

registry
    .category("website-plugins")
    .add(AiWebsiteElementSelectionPlugin.id, AiWebsiteElementSelectionPlugin);
