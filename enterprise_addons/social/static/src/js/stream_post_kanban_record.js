import { KanbanRecord } from '@web/views/kanban/kanban_record';
import { debounce } from "@web/core/utils/timing";

export const CANCEL_GLOBAL_CLICK = ["a", ".o_social_subtle_btn"].join(",");
const DEFAULT_COMMENT_COUNT = 20;

export class StreamPostKanbanRecord extends KanbanRecord {
    setup() {
        super.setup(...arguments);
        this._openComments = debounce(this.openComments.bind(this), 300, true);
    }

    //---------------------------------------
    // Handlers
    //---------------------------------------

    /**
     * @override
     */
    onGlobalClick(ev) {
        if (ev.target.closest(CANCEL_GLOBAL_CLICK)) {
            return;
        }
        this._openComments(ev);
    }

    openComments(ev) {}

    //---------
    // Getters
    //---------

    get commentCount() {
        return this.props.commentCount || DEFAULT_COMMENT_COUNT;
    }
}
