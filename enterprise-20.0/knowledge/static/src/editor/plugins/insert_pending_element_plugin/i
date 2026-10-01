import { Plugin } from "@html_editor/plugin";
import {
    isEmptyBlock,
    isParagraphRelatedElement,
    isPhrasingContent,
} from "@html_editor/utils/dom_info";
import { children } from "@html_editor/utils/dom_traversal";

export class InsertPendingElementPlugin extends Plugin {
    static id = "insertPendingElement";
    static dependencies = ["baseContainer", "history", "dom", "selection"];
    resources = {
        on_editor_started_handlers: this.insertEmbeddedBluePrint.bind(this),
    };

    insertEmbeddedBluePrint() {
        const { resModel, resId } = this.config.getRecordInfo();
        const embeddedBlueprint =
            this.services.knowledgeCommandsService.popPendingEmbeddedBlueprint({
                field: "body",
                resId,
                model: resModel,
            });
        if (embeddedBlueprint) {
            let insert;
            if (isPhrasingContent(embeddedBlueprint)) {
                insert = () => {
                    // insert phrasing content
                    const paragraph = this.dependencies.baseContainer.createBaseContainer({
                        children: [embeddedBlueprint],
                    });
                    this.dependencies.selection.setCursorEnd(this.editable);
                    this.dependencies.dom.insert(paragraph);
                    this.dependencies.history.commit();
                };
            } else {
                insert = () => {
                    // insert block content
                    const childElements = children(this.editable);
                    let cursorTarget = null;
                    if (
                        childElements.every((child) => {
                            if (isParagraphRelatedElement(child) && isEmptyBlock(child)) {
                                cursorTarget ??= child;
                                return true;
                            }
                        })
                    ) {
                        this.dependencies.selection.setCursorStart(this.editable);
                        this.dependencies.dom.insert(embeddedBlueprint);
                        this.dependencies.selection.setCursorStart(cursorTarget);
                    } else {
                        this.dependencies.selection.setCursorEnd(this.editable);
                        this.dependencies.dom.insert(embeddedBlueprint);
                        const paragraph = this.dependencies.baseContainer.createBaseContainer();
                        this.dependencies.selection.setCursorEnd(this.editable);
                        this.dependencies.dom.insert(paragraph);
                    }
                    this.dependencies.history.commit();
                };
            }
            insert();
            this.editable.addEventListener("onHistoryResetFromPeer", insert, { once: true });
        }
    }
}
