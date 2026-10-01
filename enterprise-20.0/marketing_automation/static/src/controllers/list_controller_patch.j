import { _t } from "@web/core/l10n/translation";
import { ListController } from "@web/views/list/list_controller";
import { patch } from "@web/core/utils/patch";
import { useSendToMarketingCampaign } from "../js/hooks";

patch(ListController.prototype, {
    setup() {
        super.setup();
        this.sendToMarketingCampaign = useSendToMarketingCampaign();
    },

    getStaticActionMenuItems() {
        const menuItems = super.getStaticActionMenuItems(...arguments);
        menuItems["add-participants"] = {
            icon: "work",
            description: _t("Send to Campaign"),
            sequence: 15,
            callback: async () => {
                const resModel = this.env.model.root.resModel;
                const resIds = await this.env.model.root.getResIds(true);
                await this.sendToMarketingCampaign(resModel, resIds);
            },
        };
        return menuItems;
    },
});
