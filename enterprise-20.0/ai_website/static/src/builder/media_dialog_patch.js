import { mediaDialogProps } from "@html_editor/main/media/media_dialog/media_dialog";
import { patch } from "@web/core/utils/patch";
import { t } from "@odoo/owl";

patch(mediaDialogProps, {
    imageSrc: t.string().optional(),
});
