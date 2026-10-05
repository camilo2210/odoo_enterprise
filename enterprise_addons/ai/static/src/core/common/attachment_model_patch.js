import { Attachment } from "@mail/core/common/attachment_model";

import { patch } from "@web/core/utils/patch";

patch(Attachment.prototype, {
    setup() {
        super.setup(...arguments);
        // media fields of the editor, appended to every attachment payload by
        // ir.attachment._store_attachment_fields when ai is installed
        /** @type {string|undefined} */
        this.description = undefined;
        /** @type {number|undefined} */
        this.image_height = undefined;
        /** @type {string|undefined} */
        this.image_src = undefined;
        /** @type {number|undefined} */
        this.image_width = undefined;
        /** @type {number|undefined} */
        this.original_id = undefined;
        /** @type {boolean|undefined} */
        this.public = undefined;
        /** @type {number|undefined} */
        this.res_id = undefined;
    },
});
