import { CrmShareTargetItem } from "@crm/webclient/share_target/crm_share_target_item";
import { patch } from "@web/core/utils/patch";

patch(CrmShareTargetItem.prototype, {
    async createRecordWithFile(attachments) {
        const attachmentIds = attachments.map(a => a.id);
        await this.orm.call("ir.attachment", "generate_access_token", attachmentIds);
        const actionValues = await this.orm.call(this.modelName, "action_ocr_business_cards", [[], attachmentIds], {
            context: this.context,
        });
        if (actionValues) {
            await this.action.doAction(actionValues);
            if (actionValues.tag === "display_notification") {
                return super.createRecordWithFile(...arguments);
            }
        }
    }
});
