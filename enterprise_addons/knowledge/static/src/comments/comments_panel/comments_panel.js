import { Component, onWillDestroy, onWillStart, proxy, useEffect, useOnChange } from "@odoo/owl";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { debounce } from "@web/core/utils/timing";
import { LOAD_THREADS_LIMIT } from "../../comments/comments_service";
import { KnowledgeCommentsThread } from "../comment/comment";

export class KnowledgeCommentsPanel extends Component {
    static template = "knowledge.KnowledgeCommentsPanel";
    static components = { KnowledgeCommentsThread };

    setup() {
        this.commentsService = useService("knowledge.comments");
        this.panelState = proxy(this.env.panelState);
        let threadRecordsKeys;
        this.alive = true;
        onWillDestroy(() => {
            this.alive = false;
        });
        this.state = proxy({
            mode: "unresolved", // "resolved" / "all"
            loadMoreResolved: false,
            loadMoreOpen: false,
            loading: false,
            threadIds: [],
        });
        let firstLoad = true;
        useEffect(() => {
            if (!this.alive || this.panelState.commentsState.displayMode !== "panel") {
                return;
            }
            const threadRecords = this.panelState.commentsState.threadRecords;
            const threadIds = Object.keys(threadRecords);
            const keys = threadIds.toString();
            if (keys !== threadRecordsKeys) {
                this.computeThreadIds();
                threadRecordsKeys = keys;
            }
        });
        useOnChange(
            () => [
                this.state.mode,
                this.panelState.commentsState.articleId,
                this.panelState.commentsState.displayMode,
            ],
            () => {
                if (!this.panelState.isDisplayed("comments")) {
                    return;
                }
                this.computeThreadIds();
                this.commentsService
                    .loadRecords(this.env.model.root.resId, {
                        ignoreBatch: true,
                        includeLoaded: true,
                        domain: this.domain,
                    })
                    .then((count) => {
                        if (firstLoad) {
                            firstLoad = false;
                            if (count !== undefined && count < LOAD_THREADS_LIMIT) {
                                this.sealLoadMoreState();
                            } else {
                                this.state.loadMoreOpen = true;
                                this.state.loadMoreResolved = true;
                            }
                        }
                    });
            }
        );
        onWillStart(async () => {
            // TODO ABD: test this use case
            if (
                this.env.services.action.currentController?.action?.context?.show_resolved_threads
            ) {
                this.panelState.setActivePanel("comments");
                this.mode = "resolved";
                this.env.services.action.currentController.action.context.show_resolved_threads = false;
            }
            this.isPortalUser = await user.hasGroup("base.group_portal");
            this.isInternalUser = await user.hasGroup("base.group_user");
        });
        const loadMore = debounce(this.loadMore.bind(this), 500);
        this.loadMore = () => {
            this.state.loading = true;
            loadMore();
        };
    }

    canDisplayRecord(threadId) {
        if (!this.panelState.commentsState.threadRecords[threadId]) {
            return true;
        }
        if (this.state.mode === "unresolved") {
            return !this.panelState.commentsState.threadRecords[threadId].is_resolved;
        } else if (this.state.mode === "resolved") {
            return this.panelState.commentsState.threadRecords[threadId].is_resolved;
        }
        return true;
    }

    get couldLoadMore() {
        if (this.state.mode === "unresolved") {
            return this.state.loadMoreOpen;
        } else if (this.state.mode === "resolved") {
            return this.state.loadMoreResolved;
        } else {
            return this.state.loadMoreOpen || this.state.loadMoreResolved;
        }
    }

    get domain() {
        let domain = undefined;
        if (this.state.mode === "unresolved") {
            domain = [["is_resolved", "=", false]];
        } else if (this.state.mode === "resolved") {
            domain = [["is_resolved", "=", true]];
        }
        return domain;
    }

    computeThreadIds() {
        const threadIds = [];
        for (const [threadId, record] of Object.entries(
            this.panelState.commentsState.threadRecords
        )) {
            if (
                this.state.mode === "all" ||
                (this.state.mode === "resolved" && record.is_resolved) ||
                (this.state.mode === "unresolved" && !record.is_resolved)
            ) {
                threadIds.push(threadId);
            }
        }
        this.state.threadIds = threadIds.sort((threadIdA, threadIdB) => {
            const dateA = this.panelState.commentsState.threadRecords[threadIdA].write_date;
            const dateB = this.panelState.commentsState.threadRecords[threadIdB].write_date;
            if (dateA < dateB) {
                return 1;
            } else if (dateA > dateB) {
                return -1;
            } else {
                return 0;
            }
        });
    }

    async loadMore() {
        const count = await this.commentsService.loadRecords(this.env.model.root.resId, {
            ignoreBatch: true,
            domain: this.domain,
        });
        if (count !== undefined && count < LOAD_THREADS_LIMIT) {
            this.sealLoadMoreState();
        }
        this.state.loading = false;
    }

    sealLoadMoreState() {
        if (this.state.mode === "unresolved") {
            this.state.loadMoreOpen = false;
        } else if (this.state.mode === "resolved") {
            this.state.loadMoreResolved = false;
        } else {
            this.state.loadMoreResolved = false;
            this.state.loadMoreOpen = false;
        }
    }
}
