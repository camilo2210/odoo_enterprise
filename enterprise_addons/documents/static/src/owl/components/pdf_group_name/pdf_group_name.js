import { Component, signal, t, useProps } from "@odoo/owl";

export class PdfGroupName extends Component {
    props = useProps({
        groupId: t.string(),
        name: t.string(),
        edit: t.boolean(),
        onToggleEdit: t.function().optional(),
        onEditName: t.function().optional(),
    });

    static template = "documents.component.PdfGroupName";

    // used to get the value of the input when renaming.
    nameInputRef = signal.ref();

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @public
     */
    onBlur() {
        this.props.onEditName(this.props.groupId, this.nameInputRef().value);
    }
    /**
     * @public
     */
    onClickGroupName() {
        this.props.onToggleEdit(this.props.groupId, true);
    }
    /**
     * @public
     * @param {MouseEvent} ev
     */
    onKeyDown(ev) {
        if (ev.code !== "Enter") {
            return;
        }
        ev.stopPropagation();
        this.props.onEditName(this.props.groupId, this.nameInputRef().value);
        this.props.onToggleEdit(this.props.groupId, false);
    }
}
