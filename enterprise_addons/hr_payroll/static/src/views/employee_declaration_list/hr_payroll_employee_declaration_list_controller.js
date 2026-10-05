import { proxy } from "@odoo/owl";
import {ListController} from "@web/views/list/list_controller";
import {useService} from "@web/core/utils/hooks";

export class EmployeeDeclarationListController extends ListController {
    static template = "hr_payroll.EmployeeDeclarationListController";

    setup() {
        super.setup();
        this.orm = useService("orm")
        this.action = useService("action");
        this.state = proxy({})
    }

    async onSelectionChanged() {
        await super.onSelectionChanged();

        const records = await this._getSelectedRecords();
        this.state.generateCount = records.filter(r => r.state === "draft" || r.state === "pdf_generated").length;
        this.state.postCount = records.filter(r => r.state === "pdf_generated").length;
        this.state.onlyDrafts = records.every(r => r.state === "draft");
    }
    
    async generatePdfs(){
        return this.action.doActionButton({
            type: "object",
            resModel: "hr.payroll.employee.declaration",
            name:"action_generate_pdf",
            resIds: await this.model.root.getResIds(true),
        })
    }

    async _getSelectedRecords() {
        const {root} = this.model;

        if(this.isDomainSelected) {
            const selectedIDs = await root.getResIds(true);
            return await this.orm.read(root.resModel, selectedIDs, ['state']);
        }

        if (this.hasSelectedRecords) {
            return root.selection.map((r) => r.data);
        }

        return root.records.map((r) => r.data);
    }

}
