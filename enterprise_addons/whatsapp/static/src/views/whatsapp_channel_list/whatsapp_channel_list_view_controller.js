import { ListController } from "@web/views/list/list_controller";
import { useService } from "@web/core/utils/hooks";

export class WhatsappChannelListController extends ListController {
    setup() {
        super.setup(...arguments);
        this.store = useService("mail.store");
    }

    async openRecord(record) {
        const channel = await this.store["discuss.channel"].getOrFetch(record.resId);
        if (channel) {
            return channel.open();
        }
        return super.openRecord(record);
    }
}
