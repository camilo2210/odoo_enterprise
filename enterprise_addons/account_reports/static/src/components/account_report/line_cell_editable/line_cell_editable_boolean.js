import { Component, signal, t, useProps } from "@odoo/owl";


export class AccountReportLineCellEditableBoolean extends Component {
    static template = "account_reports.AccountReportLineCellEditableBoolean";
    props = useProps({
        onChange: t.function(),
        cell: t.object(),
        audit: t.function(),
    });

    inputRef = signal.ref();

    toggleBooleanValue() {
        this.props.onChange(this.inputRef().dataset.noFormat === "0" ? 1 : 0);
    }

    get inputNoFormatValue() {
        return this.props.cell?.no_format();
    }

    get inputValue() {
        return this.props.cell?.name();
    }
}
