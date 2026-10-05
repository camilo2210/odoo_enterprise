import { proxy } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { CalendarCommonPopover } from "@web/views/calendar/calendar_common/calendar_common_popover";
import { AddressRecurrencyConfirmationDialog } from "@planning/components/address_recurrency_confirmation_dialog/address_recurrency_confirmation_dialog";
import { usePlanningRecurringDeleteAction } from "../../planning_hooks";
import { usePlanningPopoverFooter } from "@planning/components/planning_popover_footer/planning_popover_footer";

export class PlanningCalendarCommonPopover extends CalendarCommonPopover {
    static defaultFooterButtonsTemplate =
        "planning.PlanningCalendarCommonPopover.DefaultFooterButtons";

    setup() {
        super.setup(...arguments);
        this.dialogService = useService("dialog");
        this.orm = useService("orm");
        this.state = proxy({
            recurrenceUpdate: "this",
        });
        this.planningRecurrenceDeletion = usePlanningRecurringDeleteAction();
        this.footer = usePlanningPopoverFooter(() => this.props.close());
    }

    get canUnschedule() {
        return (
            !this.readonly &&
            this.props.model.isManager &&
            ["1_draft", "2_published"].includes(this.data.state) &&
            this.data.start_datetime
        );
    }

    async onUnschedule() {
        await this.orm.call(this.props.model.resModel, "action_unschedule", [this.data.id]);
        await this.props.model.load();
    }

    onDeleteEvent() {
        const record = this.props.record.rawRecord;
        if (record.repeat) {
            this.dialogService.add(AddressRecurrencyConfirmationDialog, {
                confirm: async () => {
                    await this.planningRecurrenceDeletion._actionAddressRecurrency(
                        { resId: record.id, resModel: this.props.model.resModel },
                        this.state.recurrenceUpdate
                    );
                    this.props.model.unlinkRecord(record.id);
                    this.props.close();
                },
                onChangeRecurrenceUpdate:
                    this.planningRecurrenceDeletion._setRecurrenceUpdate.bind(this),
                selected: this.state.recurrenceUpdate,
            });
        } else {
            super.onDeleteEvent();
        }
    }

    get data() {
        return this.props.record.rawRecord;
    }
}
