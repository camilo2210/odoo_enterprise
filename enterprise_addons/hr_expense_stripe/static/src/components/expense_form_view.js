import { _t } from "@web/core/l10n/translation";
import { ExpenseFormController } from "@hr_expense/views/expense_form_view";
import { patch } from "@web/core/utils/patch";

patch(ExpenseFormController.prototype, {
    get cogMenuProps() {
        const props = super.cogMenuProps;
        
        props.items.action = (props.items.action || []).filter(item => {
            if (item.name !== _t("Dispute")) {
                return true;
            }

            return this.model.root.data.card_id;
        })

        return props;
    },
});
