import { MediaDialog, mediaDialogProps } from "@html_editor/main/media/media_dialog/media_dialog";
import { patch } from "@web/core/utils/patch";
import { getData } from "@ai/utils/bus_data_getter";
import { t } from "@odoo/owl";

patch(mediaDialogProps, {
    openedFromHTMLBuilder: t.boolean().optional(),
    aiBeforeCloseHandler: t.function().optional(),
});

patch(MediaDialog.prototype, {
    async aiSaveAction({ channel, message, store }) {
        const builderData = (await getData("htmlBuilder")) || {};
        if (this.props.openedFromHTMLBuilder && builderData["callWithBuilderMutex"]) {
            builderData["callWithBuilderMutex"](async () => await super.aiSaveAction({ channel, message, store }));
        } else {
            await super.aiSaveAction({ channel, message, store });
        }
    }
});
