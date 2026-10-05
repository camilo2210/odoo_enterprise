import { Dialog } from "@web/core/dialog/dialog";
import { Component, signal, t, useProps } from "@odoo/owl";

export class ExitSplitToolsDialog extends Component {
    static components = { Dialog };

    props = useProps({
        close: t.function(),
        isEmbeddedActionApplied: t.boolean(),
        onDeleteRemainingPages: t.function(),
        onGatherRemainingPages: t.function(),
    });

    static template = "documents.ExitToolsDialog";

    setup() {
        this.modalRef = signal.ref();
    }
    /**
     * @public
     */
    deleteRemainingPages() {
        this.props.onDeleteRemainingPages();
        this.props.close();
    }
    /**
     * @public
     */
    gatherRemainingPages() {
        this.props.onGatherRemainingPages();
        this.props.close();
    }
}
