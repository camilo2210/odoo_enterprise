import { Component, useProps, t } from "@odoo/owl";
import { useBankReconciliation } from "../bank_reconciliation_service";
import { useService } from "@web/core/utils/hooks";
import { x2ManyCommands } from "@web/core/orm_plugin";

export class BankRecReconciledLineName extends Component {
    static template = "account_accountant.BankRecReconciledLineName";
    props = useProps({
        statementLine: t.object(),
        linesToReconcile: t.array(),
        moveLineId: t.string(),
        valueToDisplay: t.object(),
    });

    setup() {
        this.orm = useService("orm");
        this.bankReconciliation = useBankReconciliation();
    }

    async deleteTax(lineId, taxChanged) {
        const lineData = this.props.linesToReconcile.filter(
            (line) => line.id === parseInt(lineId)
        )[0];
        await this.orm.call("account.bank.statement.line", "edit_reconcile_line", [
            this.props.statementLine.data.id,
            lineData.id,
            { tax_ids: [[x2ManyCommands.UNLINK, taxChanged.data.id]] },
        ]);
        this.props.statementLine.load();
        this.bankReconciliation.reloadChatter();
    }
}
