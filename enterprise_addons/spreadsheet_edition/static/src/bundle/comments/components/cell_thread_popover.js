import { Thread } from "@mail/core/common/thread";
import { stores } from "@odoo/o-spreadsheet";
import { Component, proxy, t, useEffect, useProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { useSubEnv } from "@web/owl2/utils";
import { CommentsStore } from "../comments_store";
import { CellThread } from "./cell_thread";
import { SpreadsheetCommentComposer } from "./spreadsheet_comment_composer";

const { useStore } = stores;

export class CellThreadPopover extends Component {
    static template = "spreadsheet_edition.CellThreadPopover";
    static components = { Thread, CellThread, SpreadsheetCommentComposer };

    props = useProps({
        threadId: t.number().optional(),
        onClosed: t.function().optional(),
        isInteractive: t.boolean(),
        position: t.object(),
        focus: t.boolean().optional(false),
    });

    static threadModel = "spreadsheet.cell.thread";

    setup() {
        useSubEnv({
            inChatWindow: true,
        });

        /** @type {import("models").Store} */
        this.mailStore = useService("mail.store");
        this.state = proxy({
            /** @type {import("models").Thread} */
            thread: undefined,
            isValid: true,
        });
        this.loadThread(this.props.threadId);

        this.commentsStore = useStore(CommentsStore);

        useEffect(() => {
            this.loadThread(this.props.threadId);
        });
    }

    onFocused() {
        if (this.props.threadId && !this.props.isInteractive) {
            this.commentsStore.openCommentThread(this.props.threadId);
        }
    }

    showAllComments() {
        this.env.openSidePanel("Comments");
    }

    loadThread(threadId) {
        this.state.thread = this.mailStore["mail.thread"].insert({
            model: CellThreadPopover.threadModel,
            id: threadId,
        });
    }

    async insertNewThread(value, postData) {
        if (!value) {
            return;
        }
        const sheetId = this.env.model.getters.getActiveSheetId();
        const threadId = await this.env.insertThreadInSheet({ sheetId, ...this.props.position });
        this.loadThread(threadId);
        await this.state.thread.post(value, postData);
        this.commentsStore.openCommentThread(this.props.threadId);
    }
}
