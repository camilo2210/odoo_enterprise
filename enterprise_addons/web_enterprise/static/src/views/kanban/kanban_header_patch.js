import { useSticky } from "@web_enterprise/core/utils/hooks";
import { KanbanHeader } from "@web/views/kanban/kanban_header";
import { patch } from "@web/core/utils/patch";

patch(KanbanHeader.prototype, {
    setup() {
        super.setup(...arguments);
        this.sticky = useSticky(this.rootRef);
    },
});
