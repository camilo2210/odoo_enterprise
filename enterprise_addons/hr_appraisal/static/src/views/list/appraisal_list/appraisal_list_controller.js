import { ListController } from "@web/views/list/list_controller";
import { useService } from "@web/core/utils/hooks";
import { onWillStart } from "@odoo/owl";
import {
    canLaunchCampaign,
    removeLaunchButton,
} from "@hr_appraisal/views/helper/launch_campaign_helper/launch_campaign_helper";

export class AppraisalListController extends ListController {
    setup() {
        super.setup();
        this.orm = useService("orm");

        onWillStart(async () => {
            if (!(await canLaunchCampaign(this.orm))) {
                this.archInfo.headerButtons = removeLaunchButton(this.archInfo.headerButtons);
            }
        });
    }
}
