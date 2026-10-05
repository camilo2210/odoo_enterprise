import { patch } from "@web/core/utils/patch";
import { X2ManyImageField } from "@html_editor/fields/x2many_field/x2many_image_field";

patch(X2ManyImageField.prototype, {
    get mediaDialogProps() {
        const props = super.mediaDialogProps;
        props.record = this.props.record._parentRecord;
        props.originalRecordModel = this.props.record.config.resModel;
        props.originalRecordId = this.props.record.config.resId;
        props.aiSpecialActions = this.aiSpecialActions;
        return props;
    },

    get aiSpecialActions() {
        return {};
    },
});
