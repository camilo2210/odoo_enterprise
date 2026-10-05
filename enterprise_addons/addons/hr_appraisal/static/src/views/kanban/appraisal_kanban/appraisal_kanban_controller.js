import { KanbanController } from "@web/views/kanban/kanban_controller";
import { useService } from "@web/core/utils/hooks";
import { onWillStart } from "@odoo/owl";
import {
    canLaunchCampaign,
    removeLaunchButton,
} from "@hr_appraisal/views/helper/launch_campaign_helper/launch_campaign_helper";

export class AppraisalKanbanController extends KanbanController {
    setup() {
        super.setup();
        this.orm = useService("orm");

        onWillStart(async () => {
            if (!(await canLaunchCampaign(this.orm))) {
                this.headerButtons = removeLaunchButton(this.headerButtons);
            }
        });
    }
}
