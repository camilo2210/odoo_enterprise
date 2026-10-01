import { proxy } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { ListRenderer } from "@web/views/list/list_renderer";
import { PayslipActionHelper } from "../../components/payslip_action_helper/payslip_action_helper";

export class PayslipListRenderer extends ListRenderer {
    static template = "hr_payroll.PayslipListRenderer";
    static components = {
        ...ListRenderer.components,
        PayslipActionHelper,
    };

    setup() {
        super.setup();
        this.state = proxy({ payRunReactive: this.env.payRunReactive });
        this.keyPayrunOptionalFields = `payrun_${this.keyOptionalFields}`;
    }

    get payslipActionHelperProps() {
        const helperProps = {
            onClickCreate: this.props.onAdd,
        };
        helperProps.payrunId = this.state.payRunReactive.payRunId || undefined;
        return helperProps;
    }

    get showNoContentHelper() {
        const { model } = this.props.list;
        return this.props.noContentHelp && (model.useSampleModel || !model.hasData());
    }

    /** overrides **/
    /**
     * @override
     */
    getActiveColumns(list) {
        if (this.state.payRunReactive.payRunId) {
            this.allColumns = this.allColumns.map((col) => (
                col.options && 'payrun_optional' in col.options
                    ? {...col, optional: col.options.payrun_optional}
                    : col
            ));
        }
        return super.getActiveColumns(list);
    }

    saveOptionalActiveFields() {
        const storageKey = this.state.payRunReactive.payRunId
            ? this.keyPayrunOptionalFields
            : this.keyOptionalFields;
        browser.localStorage.setItem(
            storageKey,
            Object.keys(this.optionalActiveFields).filter(
                (fieldName) => this.optionalActiveFields[fieldName]
            )
        );
    }

    computeOptionalActiveFields() {
        const storageKey = this.state.payRunReactive.payRunId
            ? this.keyPayrunOptionalFields
            : this.keyOptionalFields;
        const localStorageValue = browser.localStorage.getItem(storageKey);
        const optionalColumn = this.allColumns.filter(
            (col) =>
                col.type === "field" &&
                (col.optional ||
                    (this.state.payRunReactive.payRunId && col.options?.payrun_optional))
        );
        const optionalActiveFields = {};
        if (localStorageValue !== null) {
            const localStorageOptionalActiveFields = localStorageValue.split(",");
            for (const col of optionalColumn) {
                optionalActiveFields[col.name] = localStorageOptionalActiveFields.includes(
                    col.name
                );
            }
        } else {
            for (const col of optionalColumn) {
                if (this.state.payRunReactive.payRunId && col.options?.payrun_optional) {
                    optionalActiveFields[col.name] = col.options?.payrun_optional === "show";
                }
                else {
                    optionalActiveFields[col.name] = col.optional === "show";
                }
            }
        }
        return optionalActiveFields;
    }
}
