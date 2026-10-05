import {
    SelectCreateDialog,
    selectCreateDialogProps,
} from "@web/views/view_dialogs/select_create_dialog";
import { formatMonetary } from "@web/views/fields/formatters";
import { useService } from "@web/core/utils/hooks";
import { useProps, t } from "@odoo/owl";

const { DateTime } = luxon;

export class BankRecSelectCreateDialog extends SelectCreateDialog {
    static template = "account_accountant.BankRecSelectCreateDialog";
    props = useProps({
        ...selectCreateDialogProps,
        suspenseAccountLine: t.object(),
        reference: t.string(),
        date: t.instanceOf(DateTime),
        size: t.string().optional("lg"),
    });

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.ui = useService("ui");
        this.state.remainingAmount = this.suspenseAccountLine.amount_currency;
        this.state.remainingAmountFormatted = this.remainingAmountFormatted;
        this.state.hideRemainingAmount = false;

        this.baseViewProps.onSelectionChanged = (resIds, selectedLines) => {
            this.state.resIds = resIds;
            this.changeInSelectedMoveLine(selectedLines);
        };

        this.baseViewProps.bankRecInfo = {
            date: this.formattedStatementLineDate,
            reference: this.props.reference,
            state: this.state,
            currencyId: this.suspenseAccountLine.currency_id.id,
            onSelectionChanged: (controller) => this.onSelectionChanged(controller),
        };
    }

    async changeInSelectedMoveLine(selectedLines) {
        this.state.hideRemainingAmount = false;
        if (!selectedLines?.length) {
            this.state.remainingAmount = this.suspenseAccountLine.amount_currency;
            this.state.remainingAmountFormatted = this.remainingAmountFormatted;
            return;
        }

        let selectedLinesSum = 0;
        // When the suspense currency is different from the company one, we cannot compute the remaining amount correctly
        // due to the currency rates. So in this case, when the user select multiple currencies we add the remaining amount
        if (
            this.suspenseAccountLine.currency_id.id !==
            this.suspenseAccountLine.company_currency_id.id
        ) {
            const selectedLineCurrencies = [
                ...new Set(selectedLines.map((line) => line.currency_id)),
            ];

            if (
                selectedLineCurrencies.length !== 1 ||
                (selectedLineCurrencies.length === 1 &&
                    selectedLineCurrencies[0] !== this.suspenseAccountLine.currency_id.id)
            ) {
                this.state.hideRemainingAmount = true;
                return;
            } else {
                selectedLinesSum = selectedLines.reduce(
                    (sum, line) => sum + line.amount_residual_currency,
                    0
                );
            }
        } else {
            selectedLinesSum = selectedLines.reduce((sum, line) => sum + line.amount_residual, 0);
        }
        this.state.remainingAmount = this.suspenseAccountLine.amount_currency + selectedLinesSum;
        this.state.remainingAmountFormatted = this.remainingAmountFormatted;
    }

    async onSelectionChanged(controller) {
        const resIds = await controller.model.root.getResIds(true);
        if (!resIds.length) {
            this.baseViewProps.onSelectionChanged(resIds, []);
        }

        let selectedLines;
        // When being in the list view with more element than the limit and doing a select all, the user has the
        // possibility to select more element than the limit. In this case the isDomainSelected is True
        if (controller.isDomainSelected) {
            const { resModel, context } = controller.model.root._config;
            selectedLines = await this.orm.read(
                resModel,
                resIds,
                ["amount_residual", "amount_residual_currency", "currency_id"],
                { context }
            );
        } else {
            selectedLines = Object.values(controller.model.root.records)
                .filter((record) => resIds.includes(record._config.resId))
                .map((record) => {
                    const data = record.data;
                    return {
                        amount_residual: data.amount_residual,
                        amount_residual_currency: data.amount_residual_currency,
                        currency_id: data.currency_id.id,
                    };
                });
        }
        this.baseViewProps.onSelectionChanged(resIds, selectedLines);
    }

    get suspenseAccountLine() {
        return this.props?.suspenseAccountLine;
    }

    get remainingAmountFormatted() {
        return formatMonetary(this.state.remainingAmount, {
            currencyId: this.suspenseAccountLine.currency_id.id,
        });
    }

    get formattedStatementLineDate() {
        return this.props.date?.toLocaleString({
            month: "short",
            day: "2-digit",
        });
    }
}
