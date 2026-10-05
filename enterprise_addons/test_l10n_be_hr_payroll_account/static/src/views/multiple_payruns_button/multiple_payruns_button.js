import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const viewsRegistry = registry.category("views");

if (viewsRegistry.contains("payslip_run_kanban")) {
    const payrunKanbanView = viewsRegistry.get("payslip_run_kanban");
    if(payrunKanbanView){
        payrunKanbanView.buttonTemplate = "test_l10n_be.PayrunKanbanView.Buttons";
        patch(payrunKanbanView.Controller.prototype, {
            setup() {
                super.setup();
                this.orm = useService("orm");
                this.isBelgium = false;
                onWillStart(async () => {
                    const allowedCompanyIds = this.env.searchModel?.context?.allowed_company_ids;
                    let companyId = null;
                    if(allowedCompanyIds && allowedCompanyIds.length > 0){
                        companyId = allowedCompanyIds[0];
                    }
                    if (companyId) {
                        const companyData = await this.orm.read(
                            "res.company",
                            [companyId],
                            ["country_code"]
                        );
                        if(companyData && companyData[0].country_code === 'BE'){
                            this.isBelgium = true;
                        }
                    }
                })
            },
            async multiPayButtonClick() {
                await this.actionService.doAction({
                    type: "ir.actions.act_window",
                    name: "Generate Multiple Payruns",
                    res_model: "test.l10n.be.multiple.payruns",
                    views: [[false, "form"]],
                    target: "new",
                    context: {
                        'dialog_size': "medium",
                    }
                });
            }
        });
    }
}
