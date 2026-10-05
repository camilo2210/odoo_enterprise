import {EmployeeDeclarationListController} from "../../../../../hr_payroll/static/src/views/employee_declaration_list/hr_payroll_employee_declaration_list_controller";

export class DocumentsEmployeeDeclarationListController extends EmployeeDeclarationListController{
    static template = "hr_payroll.DocumentsEmployeeDeclarationListController"

    setup() {
        super.setup();
    }
    
    async postPdfs(){
        const selectedIDs = await this.model.root.getResIds(true);
        const recordsTopost = await this.orm.read(this.model.root.resModel, selectedIDs, ['state']);
        return this.action.doActionButton({
            type: "object",
            resModel: "hr.payroll.employee.declaration",
            name: "action_post_in_documents",
            resIds: recordsTopost.filter((r) => r.state === "pdf_generated").map((r) => r.id),
        })
    }
}
