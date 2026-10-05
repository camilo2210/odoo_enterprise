import { useLayoutEffect } from "@web/owl2/utils";
import { HtmlViewer } from "@html_editor/components/html_viewer/html_viewer";
import { LocalOverlayContainer } from "@html_editor/local_overlay_container";
import { usePositionHook } from "@html_editor/position_hook";
import { onWillDestroy, proxy, signal, untrack, useEffect, useListener } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { KnowledgeCommentsHandler } from "@knowledge/comments/comments_handler/comments_handler";
import { CommentBeaconManager } from "@knowledge/comments/comment_beacon_manager";
import { KnowledgeReadOnlyHeadingLink } from "@knowledge/components/knowledge_readonly_heading_link/knowledge_readonly_heading_link";
import { useService } from "@web/core/utils/hooks";
import { uniqueId } from "@web/core/utils/functions";

export class KnowledgeHtmlViewer extends HtmlViewer {
    static template = "knowledge.KnowledgeHtmlViewer";
    static components = {
        ...HtmlViewer.components,
        LocalOverlayContainer,
    };

    setup() {
        super.setup();
        this.tocService = useService("knowledge.toc");
        this.tocState = this.tocService.getTocState();
        // Store the last toc manager to restore it when destroying the component
        this.lastTocManager = this.tocState.tocManager;
        this.tocState.tocManager = this.tocManager;
        useLayoutEffect(
            () => {
                this.tocState.tocManager = this.tocManager;
                this.tocManager.batchedUpdateStructure();
            },
            () => [this.state.value]
        );
        this.commentsService = useService("knowledge.comments");
        this.commentsState = proxy(this.commentsService.getCommentsState());
        let editorThreadsKeys;
        this.alive = true;
        useListener(window, "click", this.onWindowClick.bind(this));
        useEffect(() => {
            if (!this.alive) {
                return;
            }
            const editorThreads = this.commentsState.editorThreads;
            const keys = Object.keys(editorThreads).toString();
            if (keys !== editorThreadsKeys) {
                this.commentBeaconManager?.sortThreads();
                this.commentBeaconManager?.drawThreadOverlays();
                editorThreadsKeys = keys;
            }
        });
        onWillDestroy(() => {
            this.alive = false;
            this.tocState.tocManager = this.lastTocManager;
        });

        this.overlayRef = signal.ref();
        usePositionHook(this.readonlyElementRef, document, () => {
            this.commentBeaconManager?.drawThreadOverlays();
            this.props.config.onLayoutGeometryChange?.();
        });
        this.localOverlayContainerKey = uniqueId("html_viewer");
        this.overlayComponentsKey = uniqueId("KnowledgeCommentsHandler");
        this.linkOverlayComponentsKey = uniqueId("KnowledgeReadOnlyHeadingLink");
        useLayoutEffect(
            () => {
                let overlayContainer;
                if (
                    this.readonlyElementRef() &&
                    this.overlayRef() &&
                    this.env.model.root.data.user_permission &&
                    this.env.model.root.data.user_permission !== "none"
                ) {
                    overlayContainer = this.makeLocalOverlay("KnowledgeThreadBeacons");
                    this.overlayRef().append(overlayContainer);
                    this.commentBeaconManager = new CommentBeaconManager({
                        document,
                        source: this.readonlyElementRef(),
                        overlayContainer: overlayContainer,
                        commentsState: this.commentsState,
                        readonly: true,
                    });
                    this.commentBeaconManager.sortThreads();
                    this.commentBeaconManager.drawThreadOverlays();
                    registry
                        .category(this.localOverlayContainerKey)
                        .add(this.overlayComponentsKey, {
                            Component: KnowledgeCommentsHandler,
                            props: {
                                commentBeaconManager: this.commentBeaconManager,
                                contentRef: this.readonlyElementRef,
                            },
                        });
                }
                if (this.readonlyElementRef() && this.overlayRef()) {
                    registry
                        .category(this.localOverlayContainerKey)
                        .add(this.linkOverlayComponentsKey, {
                            Component: KnowledgeReadOnlyHeadingLink,
                            props: { readonlyElementRef: this.readonlyElementRef },
                        });
                }
                return () => {
                    overlayContainer?.remove();
                    this.commentBeaconManager?.destroy();
                    this.commentBeaconManager = undefined;
                    registry
                        .category(this.localOverlayContainerKey)
                        .remove(this.linkOverlayComponentsKey);
                    this.linkOverlayComponentsKey = uniqueId("KnowledgeReadOnlyHeadingLink");
                    registry
                        .category(this.localOverlayContainerKey)
                        .remove(this.overlayComponentsKey);
                    this.overlayComponentsKey = uniqueId("KnowledgeCommentsHandler");
                };
            },
            () => [untrack(this.readonlyElementRef), this.overlayRef(), this.state.value]
        );
    }

    onWindowClick(ev) {
        const selector = `[data-oe-local-overlay-id='KnowledgeThreadBeacons'], .o_knowledge_comment_box`;
        const closestElement = ev.target.closest(selector);
        if (!closestElement) {
            this.commentsState.activeThreadId = undefined;
        }
    }

    makeLocalOverlay(overlayId) {
        const overlayContainer = document.createElement("div");
        overlayContainer.className = `oe-local-overlay`;
        overlayContainer.setAttribute("data-oe-local-overlay-id", overlayId);
        return overlayContainer;
    }
}
