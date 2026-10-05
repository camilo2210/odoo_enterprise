import { AccrualPlugin } from "@account_reports/views/accrual_plugin";
import { onMounted, onWillStart, proxy, signal, usePlugin } from "@odoo/owl";
import { useDateTimePicker } from "@web/core/datetime/datetime_picker_hook";
import { deserializeDate, serializeDate } from "@web/core/l10n/dates";
import { render } from "@web/owl2/utils";
import { ListController } from "@web/views/list/list_controller";

const { DateTime } = luxon;


export class AccrualListController extends ListController {
    dateFilterRef = signal.ref();

    accrual = usePlugin(AccrualPlugin);

    setup() {
        super.setup();
        this.state = proxy({
            date: null,
        });
        onWillStart(async () => {
            const saved = this.accrual.entryDate;
            const date = saved ? deserializeDate(saved) : null;
            await this.setDate(date?.isValid ? date : DateTime.now());
        });
        if (this.model.config.resModel === "purchase.order.line") {
            this.model.config.fields.qty_received_at_date.aggregator = "sum";
        } else {
            this.model.config.fields.qty_delivered_at_date.aggregator = "sum";
        }
            this.model.config.fields.qty_invoiced_at_date.aggregator = "sum";
        this.model.config.fields.amount_to_invoice_at_date.aggregator = "sum";
        const getPickerProps = () => {
            const pickerProps = {
                value: this.state.date,
                type: "date",
            };
            return pickerProps;
        };
        this.dateTimePicker = useDateTimePicker({
            target: this.dateFilterRef,
            get pickerProps() {
                return getPickerProps();
            },
            onApply: (newDate) => {
                if (newDate) {
                    this.setDate(newDate);
                    render(this);
                }
            },
        });

        onMounted(async () => {
            if (this.props.context?.accrual_entry_date) {
                await this.setDate(DateTime.fromISO(this.props.context?.accrual_entry_date));
            }
        });
    }

    async openRecord(record) {
        // Instead of opening the record itself, open the parent order.
        const res_model = record.model.config.fields.order_id.relation;
        this.actionService.doAction(
            {
                name: record.data.order_id.display_name,
                type: "ir.actions.act_window",
                res_model,
                res_id: record.data.order_id.id,
                views: [[false, 'form']],
                target: "current",
            },
        );
    }

    async setDate(date) {
        this.dateAsString = serializeDate(date);
        this.model.config.context.accrual_entry_date = this.dateAsString;
        this.accrual.entryDate = this.dateAsString;
        this.state.date = date;

        delete this.model.config.currentGroups;
        this.model.config.groups = {};

        await this.model.root.load();
        this.model.notify();
    }

    get date() {
        return this.state.date.toLocaleString();
    }

    onDateClick() {
        this.dateTimePicker.open();
    }

    async beforeExecuteActionButton(clickParams) {
        if (this.dateAsString) {
            // If a date was selected, use it as the default date for the wizard.
            clickParams.buttonContext.default_date = this.dateAsString;
        }
        return super.beforeExecuteActionButton(...arguments);
    }
}
