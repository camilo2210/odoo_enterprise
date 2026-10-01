import { useAutofocus } from "@web/core/utils/hooks";
import KnowledgeIcon from "@knowledge/components/knowledge_icon/knowledge_icon";

import { Component, onWillUnmount, signal, t, useProps } from "@odoo/owl";

export class KnowledgeRenamePopover extends Component {
    static template = "knowledge.KnowledgeRenamePopover";
    static components = { KnowledgeIcon };

    props = useProps({
        record: t.object(),
        close: t.function().optional(),
    });

    autofocusRef = signal.ref();

    setup() {
        useAutofocus({ ref: this.autofocusRef });
        onWillUnmount(() => {
            this.env.updateSidebarArticles(this.props.record);
        });
    }

    onInputKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.onChangeInput(ev.target.value);
            this.props.close();
        }
    }

    async onChangeInput(title) {
        if (!title) {
            return;
        }
        await this.props.record.update({ name: title }, { save: true });
        return this.env.updateSidebarArticles(this.props.record);
    }
}
