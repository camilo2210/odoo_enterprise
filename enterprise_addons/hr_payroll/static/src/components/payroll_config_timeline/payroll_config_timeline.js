import { useDateTimePicker } from "@web/core/datetime/datetime_picker_hook";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { statusBarField, StatusBarField } from "@web/views/fields/statusbar/statusbar_field";
import { _t } from "@web/core/l10n/translation";
import { proxy, onWillStart, onWillUpdateProps, signal } from "@odoo/owl";

export class PayrollConfigTimeline extends StatusBarField {
    static template = "hr_payroll.PayrollConfigTimeline";

    datetimePickerTargetRef = signal.ref();

    /** @override **/
    setup() {
        super.setup();
        this.actionService = useService("action");
        this.orm = useService("orm");

        this.dateTimePicker = useDateTimePicker({
            target: this.datetimePickerTargetRef,
            onApply: (date) => {
                if (date) {
                    this.createVersion(date);
                }
            },
            get pickerProps() {
                return { type: "date" };
            },
        });

        this.configData = proxy({ data: [] });

        const fetchConfigData = async (record) => {
            const company_id = record.evalContext.company_id;
            if (!company_id) {
                this.configData.data = [];
                return;
            }
            this.configData.data = await this.orm.searchRead(
                "payroll.config.settings",
                [["company_id", "=", company_id]],
                ["id", "date_version"],
                { order: "date_version asc" }
            );
        };

        onWillStart(() => fetchConfigData(this.props.record));
        onWillUpdateProps((nextProps) => {
            if (nextProps.record !== this.props.record) {
                return fetchConfigData(nextProps.record);
            }
        });
    }

    async createVersion(date) {
        const [version_id] = await this.orm.call("res.company", "create_payroll_config", [
            this.props.record.evalContext.company_id,
            date,
        ]);
        await this.props.record.model.load({
            resId: version_id,
        });
    }

    onClickDateTimePickerBtn() {
        this.dateTimePicker.open();
    }

    /** @override **/
    async selectItem(item) {
        const { record } = this.props;
        await record.save();
        await this.props.record.model.load({
            resId: item.value,
        });
    }

    /** @override **/
    getAllItems() {
        const currentId = this.props.record.evalContext.id;
        return this.configData.data.map((option) => {
            const label = option.date_version
                ? luxon.DateTime.fromISO(option.date_version).toFormat("MMM dd, yyyy")
                : _t("No date");
            return {
                value: option.id,
                label,
                isFolded: false,
                isSelected: option.id === currentId,
            };
        });
    }
}

export const payrollConfigTimeline = {
    ...statusBarField,
    component: PayrollConfigTimeline,
    additionalClasses: ["o_field_statusbar", "o_records_timeline", "d-flex", "gap-1"],
};

registry.category("fields").add("payroll_config_timeline", payrollConfigTimeline);
