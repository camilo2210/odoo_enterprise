import { AccountReportController } from "@account_reports/components/account_report/controller";
import { AccountReportLineCell } from "@account_reports/components/account_report/line_cell/line_cell";

export class PartnerLedgerFollowupLineCell extends AccountReportLineCell {
    static template = "account_reports.PartnerLedgerFollowupLineCell";

    async toggleNoFollowup(ev) {
        const res = await this.orm.call(
            "account.partner.ledger.report.handler",
            "action_toggle_no_followup",
            [this.props.line.id(), this.controller.lines.map(line => line.id)]
        );
        const colIndex = this.props.line.columns.findIndex(col => col === this.props.cell)
        for (const lineId of res.updated_line_ids) {
            const line = this.controller.lines.find(line => line.id === lineId);
            line['columns'][colIndex]['no_format'] = res.updated_value;
        }
        this.controller.invalidateVisibleLines(true);
    }
}

AccountReportController.registerCustomComponent(PartnerLedgerFollowupLineCell)
