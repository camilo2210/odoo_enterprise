import { Component, proxy, signal, t, useProps } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { EMBEDDED_VIEW_LINK_STYLES } from "@knowledge/editor/embedded_components/core/embedded_view_link/embedded_view_link_style";

export class EmbeddedViewLinkEditDialog extends Component {
    static template = "knowledge.EmbeddedViewLinkEditDialog";
    static components = { Dialog };

    props = useProps({
        style: t.string(),
        close: t.function(),
        name: t.string(),
        onSave: t.function(),
    });

    inputRef = signal.ref();

    setup() {
        this.state = proxy({
            name: this.props.name,
            style: this.props.style,
        });
    }

    //--------------------------------------------------------------------------
    // GETTERS/SETTERS
    //--------------------------------------------------------------------------

    get name() {
        return this.state.name.trim();
    }

    get styles() {
        return EMBEDDED_VIEW_LINK_STYLES;
    }

    //--------------------------------------------------------------------------
    // HANDLERS
    //--------------------------------------------------------------------------

    onConfirm() {
        if (!this.name) {
            return this.inputRef()?.focus();
        }
        this.props.onSave(this.name, this.state.style);
        this.props.close();
    }

    updateStyle(style) {
        this.state.style = style;
    }
}
