import { patch } from "@web/core/utils/patch";
import { ImageFieldWithMediaDialog } from "@html_editor/fields/image_field_with_media_dialog/image_field_with_media_dialog";

patch(ImageFieldWithMediaDialog.prototype, {
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
