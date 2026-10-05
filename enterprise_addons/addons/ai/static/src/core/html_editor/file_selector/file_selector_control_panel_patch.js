import { FileSelectorControlPanel } from "@html_editor/main/media/media_dialog/file_selector";
import { t, useProps } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { getData } from "@ai/utils/bus_data_getter";
import { aiChannelDataRegistry } from "@ai/utils/ai_channel_data_registry";

patch(FileSelectorControlPanel.prototype, {
    setup() {
        super.setup();
        this.aiControlPanelProps = useProps({
            allowAI: t.boolean().optional(),
        });
        this.aiChatLauncherService = useService("aiChatLauncher");
    },
    async openAIChat(ev) {
        const mediaDialogData = (await getData("mediaDialog")) || {};
        const channel = await this.aiChatLauncherService.launchAIChat({
            interfaceKey: "media_dialog",
            channelTitle: mediaDialogData["record"]?.data.display_name,
            recordModel: mediaDialogData["originalRecordModel"],
            recordId: mediaDialogData["originalRecordId"],
            aiChatSourceId: mediaDialogData["originalRecordId"],
            referenceImagePath: mediaDialogData["imagePath"],
            aiSpecialActions: mediaDialogData["aiSpecialActions"] || {},
        });
        channel.targetRecord = mediaDialogData["record"];
        channel.fromShopExtraImage = mediaDialogData["fromShopExtraImage"];
        aiChannelDataRegistry.setData(channel.id, "imageToReplace", mediaDialogData["imageNode"]);
        aiChannelDataRegistry.setData(
            channel.id,
            "imageInsertionPosition",
            mediaDialogData["editorSelection"]
        );
        if (mediaDialogData["aiBeforeCloseHandler"]) {
            mediaDialogData["aiBeforeCloseHandler"](channel.id);
        }
        mediaDialogData["mediaDialogCloseFunction"]();
    },
});
