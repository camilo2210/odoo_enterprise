import { convertAttachmentRecordToObject } from "@ai/core/html_editor/media_dialog/media_dialog_utils";
import { aiChannelDataRegistry } from "@ai/utils/ai_channel_data_registry";
import { useDataGetter } from "@ai/utils/bus_data_getter";
import { MediaDialog } from "@html_editor/main/media/media_dialog/media_dialog";
import { renderMedia } from "@html_editor/main/media/media_dialog/media_dialog_utils";
import { t, useProps } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { imageUrl } from "@web/core/utils/urls";

patch(MediaDialog.prototype, {
    setup() {
        super.setup();

        this.aiProps = useProps({
            addHistoryStep: t.function().optional(),
            aiSave: t.function().optional(),
            aiSpecialActions: t.any().optional(),
            editorSelection: t.any().optional(),
            node: t.object().optional(),
            originalRecordId: t.any().optional(),
            originalRecordModel: t.string().optional(),
            record: t.object().optional(),
        });

        useDataGetter("mediaDialog", () => this.getMediaDialogData());
    },

    getMediaDialogData() {
        return {
            record: this.aiProps.record,
            originalRecordModel: this.aiProps.originalRecordModel,
            originalRecordId: this.aiProps.originalRecordId,
            imagePath: this.getImagePath(),
            imageNode: this.aiProps.node,
            aiSpecialActions: this.aiSpecialActions,
            mediaDialogCloseFunction: () => this.close(),
            editorSelection: this.aiProps.editorSelection,
            aiBeforeCloseHandler: this.props.aiBeforeCloseHandler,
        };
    },

    getImagePath() {
        let fullPath;
        if (this.props.imageSrc) {
            fullPath = `${window.location.origin}${this.props.imageSrc}`;
        }
        // If an image is replaced on website but the changes aren't saved yet, then currentSrc will be the
        // base64 content of the image and not an actual url. Thus, originalSrc must take precedence over currentSrc.
        else if (this.props.media?.dataset.originalSrc) {
            fullPath = `${window.location.origin}${this.props.media.dataset.originalSrc}`;
        } else if (this.props.media?.currentSrc) {
            fullPath = this.props.media.currentSrc;
        } else if (this.aiProps.originalRecordModel && this.aiProps.originalRecordId) {
            fullPath = imageUrl(
                this.aiProps.originalRecordModel,
                this.aiProps.originalRecordId,
                "image_1024"
            );
        }
        if (!fullPath) {
            return "";
        }
        const urlObject = new URL(fullPath);
        return urlObject.pathname + urlObject.search;
    },

    get aiSpecialActions() {
        return Object.keys(this.aiProps.aiSpecialActions || {}).length
            ? this.aiProps.aiSpecialActions
            : { useThis: (content) => this.aiSaveAction(content) };
    },

    async aiSaveAction({ channel, message, store }) {
        const imageAttachment = message.attachment_ids.filter((attachment) =>
            attachment.mimetype.includes("image")
        )[0];
        const imageAttachmentObject = convertAttachmentRecordToObject(imageAttachment);
        imageAttachmentObject.mediaType = "attachment";
        const oldMediaNode = aiChannelDataRegistry.getData(channel.id, "imageToReplace");
        const element = (
            await renderMedia({
                orm: store.env.services.orm,
                activeTab: "IMAGES",
                availableTabs: this.tabs,
                oldMediaNode: oldMediaNode,
                selectedMedia: [imageAttachmentObject],
                extraClassesToAdd: this.extraClassesToAdd(),
                extraClassesToRemove: this.initialIconClasses,
            })
        )[0];
        element.dataset.aiChannelId = channel.id;
        const saveFn = this.aiProps.aiSave || this.props.save;
        await saveFn(element, [imageAttachmentObject], "IMAGES", oldMediaNode);

        this.aiProps.addHistoryStep?.();
    },
});
