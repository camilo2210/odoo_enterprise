import { patch } from "@web/core/utils/patch";
import { ExpenseListController } from "@hr_expense/views/list";

patch(ExpenseListController.prototype, {
    displayRemove() {
        const records = this.model.root.selection;
        return (
            this.userIsAccountInvoicing && records.length
            && records.every((record) =>
                !!record.data.payslip_id
                && record.data.payment_mode === 'payslip_account'
                && !["posted", "in_payment", "paid"].includes(record.data.state)
        )
    );
    }
});
