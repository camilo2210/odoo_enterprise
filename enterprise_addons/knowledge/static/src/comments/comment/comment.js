import { KnowledgeCommentsPopover } from "@knowledge/comments/comments_popover/comments_popover";
import { KnowledgeCommentCreatorComposer } from "@knowledge/comments/composer";
import { KnowledgeThread } from "@knowledge/comments/knowledge_thread";
import { Composer } from "@mail/core/common/composer";
import {
    computed,
    Component,
    onWillDestroy,
    onWillStart,
    proxy,
    signal,
    t,
    useEffect,
    useOnChange,
    useProps,
} from "@odoo/owl";
import { isBrowserChrome } from "@web/core/browser/feature_detection";
import { usePopover } from "@web/core/popover/popover_hook";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { scrollTo } from "@web/core/utils/scrolling";
import { imageUrl } from "@web/core/utils/urls";
import { useSubEnv } from "@web/owl2/utils";
import { CommentAnchorText } from "./comment_anchor_text";

const DEFAULT_ANCHOR_TEXT_SIZE = 50;
export const MIN_THREAD_WIDTH = 300;

export class KnowledgeCommentsThread extends Component {
    static components = {
        CommentAnchorText,
        Composer,
        KnowledgeThread,
        KnowledgeCommentCreatorComposer,
    };
    static template = "knowledge.KnowledgeCommentsThread";

    props = useProps({
        threadId: t.string(),
        horizontalDimensions: t.object().optional(),
        top: t.number().optional(),
    });

    threadHeights = useProps.static(
        "threadHeights",
        t.record(t.object({ height: t.number() })).optional({})
    );

    targetRef = signal.ref();
    threadScrollableRef = signal.ref();

    setup() {
        this.commentsService = useService("knowledge.comments");
        this.commentsState = proxy(this.commentsService.getCommentsState());
        let previousThreadId;
        this.alive = true;
        // Cache the last non undefined value for threadRecord. The commentsState
        // resets its threadRecords collection eg when the current article
        // changes (onWillUpdateProps), however at that point, instances of
        // this class are not destroyed yet, and many reactive constructions
        // (eg message_actions) are still subscribed to changes on the current
        // threadRecord. With this cache system, even if the commentsState is
        // reset, subscribers are not affected as the computed signal returns
        // the cached value.
        let threadRecord;
        this.threadRecord = computed(() => {
            const updatedThreadRecord = this.commentsState.threadRecords[this.props.threadId];
            if (updatedThreadRecord !== undefined) {
                threadRecord = updatedThreadRecord;
            }
            return threadRecord;
        });
        useEffect(() => {
            if (!this.alive) {
                return;
            }
            if (previousThreadId !== this.commentsState.activeThreadId) {
                if (previousThreadId === this.props.threadId && this.editorThread) {
                    this.editorThread.onActivate(new CustomEvent("knowledge.deactivateThread"));
                }
                previousThreadId = this.commentsState.activeThreadId;
            }
        });
        onWillDestroy(() => {
            this.alive = false;
        });
        this.state = proxy({
            hasFullAnchorText: false,
        });
        useSubEnv({
            // We need to unset the chatter inside the env of the child Components
            // because this Object contains values and methods that are linked to the form view's
            // main chatter. By doing this we distinguish the main chatter from the comments.
            inChatter: false,
            chatter: false,
            closeThread: this.updateResolveState.bind(this, true),
            inKnowledge: true,
            isResolved: this.isResolved.bind(this),
            openThread: this.updateResolveState.bind(this, false),
        });
        this.popover = usePopover(KnowledgeCommentsPopover, {
            closeOnClickAway: true,
            onClose: () => {
                this.onClosePopover();
            },
            position: "left-start",
            popoverClass: "o_knowledge_comments_popover d-flex flex-column rounded-3 shadow-sm",
            withScope: true,
        });
        const onActivate = (ev) => {
            switch (ev.type) {
                case "click":
                    this.activateThread();
                    break;
                case "knowledge.deactivateThread":
                    this.focusOut();
                    break;
            }
        };
        const onFocus = (ev) => {
            switch (ev.type) {
                case "mouseenter":
                    this.focusIn();
                    break;
                case "mouseleave":
                    this.focusOut();
                    break;
            }
        };
        useOnChange(
            () => [this.editorThread],
            (editorThread) => {
                if (!editorThread) {
                    return;
                }
                editorThread.onActivateMap.set("main", onActivate);
                editorThread.onFocusMap.set("main", onFocus);
                return () => {
                    editorThread.onActivateMap.delete("main");
                    editorThread.onFocusMap.delete("main");
                };
            }
        );
        if (this.commentsState.displayMode === "handler") {
            const setTargetHeight = (target) => {
                const targetRect = target.getBoundingClientRect();
                if (!(this.props.threadId in this.threadHeights)) {
                    this.threadHeights[this.props.threadId] = {
                        height: undefined,
                    };
                }
                this.threadHeights[this.props.threadId].height = targetRect.height;
            };
            useEffect(() => {
                const target = this.targetRef();
                if (target) {
                    const observer = new ResizeObserver((entries) => {
                        for (const entry of entries) {
                            if (entry.target) {
                                setTargetHeight(entry.target);
                            }
                        }
                    });
                    observer.observe(target);
                    setTargetHeight(target);
                    return () => observer.disconnect();
                }
            });
            useEffect(() => {
                if (
                    this.editorThread &&
                    (this.editorThread.threadId === "undefined" ||
                        this.commentsState.shouldOpenActiveThread) &&
                    this.targetRef() &&
                    this.isActive
                ) {
                    this.commentsState.shouldOpenActiveThread = false;
                    if (this.smallUI) {
                        this.openPopover();
                    }
                }
            });
            useEffect(() => {
                if (!this.smallUI && this.popover.isOpen) {
                    this.popover.close();
                }
            });
        }
        if (this.props.threadId === "undefined") {
            onWillStart(() => {
                this.commentsService.loadThreads([this.props.threadId]);
            });
        } else {
            // commentsState.threadRecords is reset onWillUpdateProps when
            // the articleId changes, loadRecords should not be called
            // during this transient state (this component is destined to be
            // destroyed).
            const articleId = this.commentsState.articleId;
            useOnChange(
                () => [this.commentsState.displayMode],
                () => {
                    if (
                        articleId === this.commentsState.articleId &&
                        !(this.props.threadId in this.commentsState.threadRecords)
                    ) {
                        this.commentsService.loadRecords(this.env.model.root.resId, {
                            threadId: this.props.threadId,
                        });
                    }
                }
            );
            useOnChange(
                () => [this.threadRecord()],
                (threadRecord) => {
                    if (!threadRecord || this.props.threadId in this.commentsState.threads) {
                        return;
                    }
                    this.commentsService.loadThreads([this.props.threadId]);
                    this.thread.fetchNewMessages().then(() => {
                        if (this.editorThread?.isProtected()) {
                            return;
                        }
                        let isEmpty = true;
                        for (const message of this.thread.messages) {
                            if (message.message_type === "comment" && !message.isEmpty) {
                                isEmpty = false;
                                break;
                            }
                        }
                        if (isEmpty) {
                            this.commentsService.deleteThread(this.props.threadId);
                        }
                    });
                }
            );
        }
        onWillDestroy(() => {
            if (this.isActive) {
                this.commentsState.activeThreadId = undefined;
            }
            this.commentsState.focusedThreads.delete(this.props.threadId);
        });
    }

    get hasLoaded() {
        return (
            this.props.threadId === "undefined" ||
            (this.props.threadId in this.commentsState.threadRecords &&
                this.props.threadId in this.commentsState.threads)
        );
    }

    get hasAllDimensions() {
        return (
            this.props.top !== undefined &&
            this.props.horizontalDimensions !== undefined &&
            this.props.horizontalDimensions.left !== undefined &&
            this.props.horizontalDimensions.width !== undefined
        );
    }

    get style() {
        if (this.commentsState.displayMode === "panel") {
            return "";
        }
        return `
            position: absolute;
            top: ${this.props.top}px;
            left: ${this.props.horizontalDimensions.left}px;
            width: ${this.props.horizontalDimensions.width}px;
            transition: top 0.3s, left 0.2s, filter 0.2s;
            z-index: ${this.isActive ? 1 : "auto"};
            filter: ${
                !this.smallUI ||
                this.hasFocus ||
                (!this.commentsState.activeThreadId && !this.commentsState.focusedThreads.size)
                    ? "none"
                    : "grayscale(50%) contrast(50%)"
            };
        `;
    }

    /**@see EditorThreadInfo */
    get editorThread() {
        return this.commentsState.editorThreads[this.props.threadId];
    }

    get authorUrl() {
        if (this.thread?.messages?.length) {
            return this.thread.messages.at(-1).author.avatarUrl;
        }
        return imageUrl("res.users", user.userId, "avatar_128");
    }

    get anchorText() {
        let text = this.fullAnchorText;
        const brIndex = text.indexOf("<br>");
        const excludeIndex = brIndex === -1 ? DEFAULT_ANCHOR_TEXT_SIZE : brIndex;
        if (text.length > excludeIndex) {
            text = text.substring(0, excludeIndex) + "...";
        }
        return text;
    }

    get fullAnchorText() {
        let text;
        if (!this.editorThread) {
            text = this.threadRecord()?.article_anchor_text || "";
        } else {
            text = this.editorThread.anchorText;
        }
        return text.replaceAll("\n", "<br>");
    }

    get hasFocus() {
        return this.commentsState.hasFocus(this.props.threadId);
    }

    get isActive() {
        return this.commentsState.activeThreadId === this.props.threadId;
    }

    get showReadMore() {
        const anchorText = this.anchorText;
        const fullAnchorText = this.fullAnchorText;
        return fullAnchorText.length > 0 && anchorText.length !== fullAnchorText.length;
    }

    /**@see Thread */
    get thread() {
        return this.commentsState.threads[this.props.threadId];
    }

    get smallUI() {
        return (
            this.commentsState.displayMode === "handler" &&
            this.props.horizontalDimensions.width < MIN_THREAD_WIDTH
        );
    }

    activateThread() {
        this.commentsState.activeThreadId = this.props.threadId;
        if (this.smallUI) {
            this.openPopover();
        }
    }

    /**
     * Used for the message actions
     */
    isResolved() {
        if (this.props.threadId === "undefined") {
            return false;
        }
        return this.threadRecord().is_resolved;
    }

    onClick(ev) {
        if (this.editorThread) {
            this.editorThread.onActivate(ev);
        } else {
            this.activateThread();
        }
    }

    focusIn() {
        this.commentsState.focusedThreads.add(this.props.threadId);
    }

    focusOut() {
        this.commentsState.focusedThreads.delete(this.props.threadId);
    }

    onMouseEnter(ev) {
        if (this.editorThread) {
            this.editorThread.onFocus(ev);
        } else {
            this.focusIn();
        }
    }

    onMouseLeave(ev) {
        if (this.editorThread) {
            this.editorThread.onFocus(ev);
        } else {
            this.focusOut();
        }
    }

    openPopover() {
        if (!this.popover.isOpen) {
            const popoverProps = {
                threadId: this.props.threadId,
            };
            if (this.targetRef()) {
                this.popover.open(this.targetRef(), popoverProps);
            }
        }
    }

    onClosePopover() {
        this.focusOut();
    }

    showEditorAnchor() {
        if (!this.editorThread) {
            return;
        }
        if (isBrowserChrome()) {
            scrollTo(this.editorThread.beaconPair.start, {
                behavior: "smooth",
            });
        } else {
            this.editorThread.beaconPair.start.scrollIntoView({
                behavior: "smooth",
                block: "center",
            });
        }
    }

    async updateResolveState(value) {
        const changed = await this.commentsService.updateResolveState(this.props.threadId, value);
        if (changed && this.commentsState.displayMode === "panel") {
            await this.thread.fetchNewMessages();
        }
    }

    onCreateThreadCallback(thread) {
        if (thread) {
            this.commentsState.editorThreads[thread.id]?.select();
        }
    }
}
