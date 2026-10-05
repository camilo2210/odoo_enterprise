import { useSubEnv } from "@web/owl2/utils";
import { asyncComputed, Component, onWillStart, t, useProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Thread } from "@mail/core/common/thread";
import { Composer } from "@mail/core/common/composer";
import { SpreadsheetCommentComposer } from "./spreadsheet_comment_composer";

export class CellThread extends Component {
    static template = "spreadsheet_edition.CellThread";
    static components = { Thread, Composer, SpreadsheetCommentComposer };

    static threadModel = "spreadsheet.cell.thread";

    props = useProps({
        threadId: t.number(),
        edit: t.boolean(),
    });

    setup() {
        useSubEnv({
            inChatWindow: true,
            chatter: {},
        });
        /** @type {import("models").Store} */
        this.mailStore = useService("mail.store");
        this.thread = asyncComputed(async () => {
            const thread = this.mailStore["mail.thread"].insert({
                model: CellThread.threadModel,
                id: this.props.threadId,
            });
            thread.fetchNewMessages();
            return thread;
        });

        onWillStart(() => this.thread.currentPromise());
    }
}
