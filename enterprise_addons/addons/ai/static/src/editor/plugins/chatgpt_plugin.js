import { _t } from "@web/core/l10n/translation";
import { Plugin } from "@html_editor/plugin";
import {
    firstLeaf,
    lastLeaf,
    closestElement,
    getCommonAncestor,
} from "@html_editor/utils/dom_traversal";
import { withSequence } from "@html_editor/utils/resource";
import { isContentEditable } from "@html_editor/utils/dom_info";
import { nodeSize } from "@html_editor/utils/position";
import { unwrapContents } from "@html_editor/utils/dom";
import { MAIN_PLUGINS } from "@html_editor/plugin_sets";
import { user } from "@web/core/user";
import { MAIL_CORE_PLUGINS } from "@mail/core/common/plugin/plugin_sets";

export class ChatGPTPlugin extends Plugin {
    static id = "chatgpt";
    static dependencies = [
        "baseContainer",
        "selection",
        "history",
        "dom",
        "sanitize",
        "dialog",
        "split",
        "format",
    ];
    static shared = ["openDialog"];
    resources = {
        user_commands: [
            {
                id: "openChatGPTDialog",
                title: _t("AI"),
                description: _t("Generate or transform content with AI"),
                run: this.openDialog.bind(this),
                isAvailable: () => user.isInternalUser,
            },
        ],
        toolbar_groups: withSequence(50, {
            id: "ai",
        }),
        toolbar_items: [
            {
                id: "chatgpt",
                groupId: "ai",
                commandId: "openChatGPTDialog",
                namespaces: ["compact", "expanded"],
                icon: "o_ai_icon",
                isDisabled: this.isNotReplaceableByAI.bind(this),
            },
        ],
        powerbox_categories: withSequence(70, { id: "ai", name: _t("AI Tools") }),
        powerbox_items: {
            keywords: [_t("AI")],
            categoryId: "ai",
            commandId: "openChatGPTDialog",
            icon: "wand_stars",
        },
        power_buttons: withSequence(20, {
            commandId: "openChatGPTDialog",
            icon: "o_ai_icon",
        }),
        clean_for_save_processors: this.cleanForSave.bind(this),
    };

    isNotReplaceableByAI(selection = this.dependencies.selection.getEditableSelection()) {
        if (selection.isCollapsed) {
            return false;
        }
        const isEmpty = !selection.toString().replace(/\s+/g, "");
        const cannotReplace = this.dependencies.selection
            .getTargetedNodes()
            .find((el) => this.dependencies.split.isUnsplittable(el) || !isContentEditable(el));
        return cannotReplace || isEmpty;
    }

    createSelectBlock(nodes) {
        const connectedNodes = nodes.filter((node) => node.isConnected);
        if (!connectedNodes.length) {
            return;
        }
        const firstInsertedNode = connectedNodes[0];
        const lastInsertedNode = connectedNodes[connectedNodes.length - 1];
        const anchorNode = firstLeaf(firstInsertedNode);
        const focusNode = lastLeaf(lastInsertedNode);
        const commonAncestor = getCommonAncestor([anchorNode, focusNode]);
        return {
            anchorNode: anchorNode,
            anchorOffset: 0,
            focusNode: focusNode,
            focusOffset: nodeSize(focusNode),
            startContainer: anchorNode,
            startOffset: 0,
            endContainer: focusNode,
            endOffset: nodeSize(focusNode),
            commonAncestorContainer: commonAncestor,
        };
    }

    async openDialog(params = {}) {
        const selection = this.dependencies.selection.getEditableSelection();
        const dialogParams = {
            insert: (content, selection) => {
                if (selection) {
                    this.dependencies.selection.setSelection(selection);
                    this.dependencies.format.removeSelectionFormats();
                }
                const insertedNodes = this.dependencies.dom.insert(content);
                this.dependencies.history.commit();
                // Add a frame around the inserted content to highlight it for 2
                // seconds.
                const start = insertedNodes?.length && closestElement(insertedNodes[0]);
                const end =
                    insertedNodes?.length &&
                    closestElement(insertedNodes[insertedNodes.length - 1]);
                if (start && end) {
                    const divContainer = this.editable.parentElement;
                    let [parent, left, top] = [
                        start.offsetParent,
                        start.offsetLeft,
                        start.offsetTop - start.scrollTop,
                    ];
                    while (parent && !parent.contains(divContainer)) {
                        left += parent.offsetLeft;
                        top += parent.offsetTop - parent.scrollTop;
                        parent = parent.offsetParent;
                    }
                    let [endParent, endTop] = [end.offsetParent, end.offsetTop - end.scrollTop];
                    while (endParent && !endParent.contains(divContainer)) {
                        endTop += endParent.offsetTop - endParent.scrollTop;
                        endParent = endParent.offsetParent;
                    }
                    const div = document.createElement("div");
                    div.classList.add("o-chatgpt-content");
                    const FRAME_PADDING = 3;
                    div.style.left = `${left - FRAME_PADDING}px`;
                    div.style.top = `${top - FRAME_PADDING}px`;
                    div.style.width = `${
                        Math.max(start.offsetWidth, end.offsetWidth) + FRAME_PADDING * 2
                    }px`;
                    div.style.height = `${endTop + end.offsetHeight - top + FRAME_PADDING * 2}px`;
                    divContainer.prepend(div);
                    setTimeout(() => div.remove(), 2000);
                }
            },
            selectPreviousInsertion: (selectionId) => {
                const targetElement = this.editable.querySelector(
                    `[data-ai-selection-id="${selectionId}"]`
                );
                if (targetElement) {
                    return this.createSelectBlock([targetElement]);
                }
            },
            ...params,
        };
        dialogParams.baseContainer = this.dependencies.baseContainer.getDefaultNodeName();
        // collapse to end
        let callerComp,
            recordModel,
            recordId,
            recordData,
            recordFields,
            callerId,
            channelTitle,
            textSelection;
        const { resModel, resId, data, fields, id } = this.config.getRecordInfo();
        const textOfEditable = this.editable.innerText;
        if (selection.isCollapsed) {
            if (resModel === "mail.compose.message") {
                callerComp = "mail_composer";
                recordModel = data.model;
                recordId = Number(data.res_ids.slice(1, -1)); // resIds should look like so `[id]`, the slice and cast allows to extract the id
                recordData = data;
                channelTitle = data.subject;
                callerId = id;
            } else {
                callerComp = params.callerComp || "html_field_record";
                recordModel = resModel;
                recordId = resId;
                recordData = data;
                recordFields = fields;
                channelTitle = params.channelTitle || data?.display_name || _t("Editor");
                callerId = resId || id;
            }
            textSelection = {
                selectionId: `ai-selection-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
            };
        } else {
            callerComp = "html_field_text_select";
            recordModel = resModel;
            recordId = resId;
            recordData = data;
            recordFields = fields;
            channelTitle = _t("Text Selection");
            callerId = resId || id;

            const textOfSelection = selection.toString();
            const selectionId = `ai-selection-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
            const wrapper = this.document.createElement("span");
            wrapper.dataset.aiSelectionId = selectionId;
            wrapper.classList.add("o_ai_selection_wrapper");

            const range = this.document.getSelection().getRangeAt(0);
            const contents = range.extractContents();
            wrapper.appendChild(contents);
            range.insertNode(wrapper);

            textSelection = {
                selectionId: selectionId,
                textContent: textOfSelection,
            };
        }
        await this.services.aiChatLauncher.launchAIChat({
            interfaceKey: callerComp,
            recordModel: recordModel,
            recordId: recordId,
            originalRecordData: recordData,
            originalRecordFields: recordFields,
            aiSpecialActions: {
                insert: dialogParams.insert,
                selectPreviousInsertion: dialogParams.selectPreviousInsertion,
            },
            channelTitle: channelTitle,
            aiChatSourceId: callerId,
            textSelection: textSelection,
            textOfEditable: textOfEditable,
        });
        if (this.services.ui.isSmall) {
            // TODO: Find a better way and avoid modifying range
            // HACK: In the case of opening through dropdown:
            // - when dropdown open, it keep the element focused before the open
            // - when opening the dialog through the dropdown, the dropdown closes
            // - upon close, the generic code of the dropdown sets focus on the kept element (in our case, the editable)
            // - we need to remove the range after the generic code of the dropdown is triggered so we hack it by removing the range in the next tick
            Promise.resolve().then(() => {
                // If the dialog is opened on a small screen, remove all selection
                // because the selection can be seen through the dialog on some devices.
                this.document.getSelection()?.removeAllRanges();
            });
        }
    }

    cleanForSave(root) {
        const aiInsertedElements = root.querySelectorAll(`span[data-ai-selection-id]`);
        const elements = [...aiInsertedElements];
        for (const element of elements) {
            unwrapContents(element);
        }
        return root;
    }

    destroy() {
        const { resModel } = this.config.getRecordInfo();
        if (resModel !== "mail.compose.message") {
            this.services["mail.store"].aiInsertButtonTarget = false;
        }
        super.destroy();
    }
}

MAIN_PLUGINS.push(ChatGPTPlugin);
MAIL_CORE_PLUGINS.push(ChatGPTPlugin);
