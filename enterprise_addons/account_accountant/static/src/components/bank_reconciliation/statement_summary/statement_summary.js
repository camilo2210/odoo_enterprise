import { Component, useProps, t } from "@odoo/owl";

export const bankRecStatementSummaryProps = {
    record: t.object().optional(),
    label: t.string().optional(),
    amount: t.string().optional(),
    action: t.function(),
    actionReview: t.function().optional(),
    journalId: t.number().optional(),
    isValid: t.boolean().optional(true),
    journalIsInvalid: t.boolean().optional(),
    problemDescription: t.string().optional(),
    isReviewFilterActive: t.boolean().optional(),
};

export class BankRecStatementSummary extends Component {
    static template = "account_accountant.BankRecStatementSummary";

    props = useProps(bankRecStatementSummaryProps);

    actionApplyInvalidStatement() {
        const facets = this.env.searchModel.facets;
        const searchItems = this.env.searchModel.searchItems;
        const invalidStatementFilter = Object.values(searchItems).find(
            (i) => i.name == "invalid_statement"
        );
        const invalidStatementFacet = facets.filter(
            (i) => i.groupId == invalidStatementFilter.groupId
        );
        if (
            invalidStatementFacet.length == 0 ||
            !invalidStatementFacet[0].values.includes(invalidStatementFilter.description)
        ) {
            this.env.searchModel.toggleSearchItem(invalidStatementFilter.id);
        }
    }

    get formatStatementDates() {
        if (!this.props.record) {
            return {};
        }
        const statementLines = this.env.model.root.records.filter(
            (line) => line.data.statement_id.id === this.props.record.statementId
        );
        if (statementLines.length > 1) {
            const dateFrom = statementLines.at(-1).data.date.toLocaleString({
                month: "numeric",
                day: "2-digit",
            });
            const dateTo = statementLines.at(0).data.date.toLocaleString({
                month: "numeric",
                day: "2-digit",
            });
            if (dateFrom === dateTo) {
                return { dateFrom: dateFrom };
            }
            return { dateFrom: dateFrom, dateTo: dateTo };
        }
        const date = statementLines.at(0).data.date.toLocaleString({
            month: "numeric",
            day: "2-digit",
        });
        return { dateFrom: date };
    }

    get label() {
        return this.props.record?.name || this.props.label || "";
    }

    get amount() {
        return this.props.record?.amount || this.props.amount || "";
    }
}
