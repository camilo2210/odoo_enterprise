import { registry } from "@web/core/registry";
import { ExpenseFormView } from "@hr_expense/views/expense_form_view";
import { ExtractMixinFormRenderer } from "@iap_extract/components/manual_correction/form_renderer";

export class HrExpenseFormRenderer extends ExtractMixinFormRenderer(ExpenseFormView.Renderer) {
    setup() {
        super.setup();

        this.recordModel = "hr.expense";
    }
}

export const HrExpenseFormRendererFormViewExtract = {
    ...ExpenseFormView,
    Renderer: HrExpenseFormRenderer,
};

registry.category("views").add("hr_expense_form", HrExpenseFormRendererFormViewExtract);
