import { Composer } from "@mail/core/common/composer";
import { KnowledgeCommentCreatorComposer } from "@knowledge/comments/composer";
import { KnowledgeThread } from "@knowledge/comments/knowledge_thread";
import { useService } from "@web/core/utils/hooks";
import { Component, proxy, signal, t, types, useProps } from "@odoo/owl";

export class KnowledgeCommentsPopover extends Component {
    static template = "knowledge.KnowledgeCommentsPopover";
    static components = { Composer, KnowledgeThread, KnowledgeCommentCreatorComposer };

    props = useProps({
        threadId: t.string(),
        close: t.function(),
    });

    setup() {
        this.commentsService = useService("knowledge.comments");
        this.commentsState = proxy(this.commentsService.getCommentsState());
        this.rootRef = signal(null, { type: types.instanceOf(HTMLDivElement) });
    }

    onPostCallback() {
        this.props.close();
    }

    onCreateThreadCallback(thread) {
        if (thread) {
            this.commentsState.editorThreads[thread.id]?.select();
        }
    }

    get thread() {
        return this.commentsState.threads[this.props.threadId];
    }
}
