import { ListController } from "@web/views/list/list_controller";
import { useOpenPayRun } from "../payslip_run_hook";

export class PayRunListController extends ListController {
    setup() {
        super.setup();
        this.openPayRun = useOpenPayRun();
    }

    // open the pay run creation dialog instead of switching to the form view
    async createRecord() {
        await this.openPayRun({});
    }
}
