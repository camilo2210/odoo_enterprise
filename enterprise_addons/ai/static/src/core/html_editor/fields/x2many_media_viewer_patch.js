import { patch } from "@web/core/utils/patch";
import { X2ManyMediaViewer } from "@html_editor/fields/x2many_field/x2many_media_viewer";

patch(X2ManyMediaViewer.prototype, {
    get mediaDialogProps() {
        const props = super.mediaDialogProps;
        props.record = this.props.record;
        props.originalRecordModel = this.props.record.model.config.resModel;
        props.originalRecordId = this.props.record.model.config.resId;
        props.aiSpecialActions = this.aiSpecialActions;
        return props;
    },

    get aiSpecialActions() {
        return {};
    },
});
