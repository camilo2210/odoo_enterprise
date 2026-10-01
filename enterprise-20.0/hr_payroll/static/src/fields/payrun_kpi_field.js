import { Component, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { getCurrency } from "@web/core/currency";
import { localization } from "@web/core/l10n/localization";
import { formatMonetary } from "@web/views/fields/formatters";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class PayRunKpiField extends Component {
    static template = "hr_payroll.PayRunKpiField";
    props = useProps(standardFieldProps);

    get amount() {
        const { name, record } = this.props;
        const currencyField = record.fields[name]?.currency_field || "currency_id";
        const currencyValue = record.data[currencyField];
        const currencyId = currencyValue?.id ?? currencyValue;

        const formatted = formatMonetary(record.data[name] ?? 0, {
            currencyId,
            noSymbol: true,
        });
        const separator = localization.decimalPoint;
        const index = formatted.lastIndexOf(separator);
        return {
            symbol: getCurrency(currencyId)?.symbol ?? "",
            units: index === -1 ? formatted : formatted.slice(0, index),
            decimals: index === -1 ? "" : formatted.slice(index),
        };
    }
}

export const payRunKpiField = {
    component: PayRunKpiField,
    displayName: _t("Pay Run KPI"),
    supportedTypes: ["monetary", "float"],
};

registry.category("fields").add("payrun_kpi", payRunKpiField);
