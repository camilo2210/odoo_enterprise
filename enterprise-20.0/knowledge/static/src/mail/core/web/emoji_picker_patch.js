import { t } from "@odoo/owl";
import { EmojiPicker, emojiPickerProps } from "@web/core/emoji_picker/emoji_picker";

import { patch } from "@web/core/utils/patch";

emojiPickerProps.hasRemoveFeature = t.any().optional();

patch(EmojiPicker.prototype, {
    removeEmoji() {
        this.props.onSelect(false);
        this.gridRef().scrollTop = 0;
        this.props.close?.();
        this.props.onClose?.();
    },
});
