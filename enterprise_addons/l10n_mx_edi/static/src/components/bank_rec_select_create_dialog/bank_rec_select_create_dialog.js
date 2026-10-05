import { BankRecSelectCreateDialog } from "@account_accountant/components/bank_reconciliation/search_dialog/search_dialog";
import { patch } from "@web/core/utils/patch";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import { _t } from "@web/core/l10n/translation";

patch(BankRecSelectCreateDialog.prototype, {
    /**
     * Obtains and triggers action to register and apply a factoring payment
     * on selected lines.
     */
    async onSelectAndDistribute(ev) {
        await this.dialogService.add(FormViewDialog, {
            resModel: "l10n_mx_edi.register.factoring",
            size: "lg",
            title: _t("Distribute Payment"),
            context: {
                move_line_ids: this.state.resIds,
                statement_line_id: this.props.context.statement_line_id,
            },
            onRecordSave: async (record) => {
                const saved = await record.save({ reload: true });
                if (!saved) {
                    return false;
                }
                const result = await this.orm.call(
                    "l10n_mx_edi.register.factoring",
                    "action_apply_factoring",
                    [record.resId],
                );

                if (result) {
                    this.state.resIds = []; // We remove the selected ids to avoid adding them when 'set_line_bank_statement_line' is called
                    this.select();
                }
                return result;
            },
        });
    },

    get canUseFactoring() {
        return this.props.context.can_use_factoring;
    },
});
