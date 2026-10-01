import { _t } from "@web/core/l10n/translation";
import { Component, t, useProps } from "@odoo/owl";
import { ConfirmationDialog, deleteConfirmationMessage } from "@web/core/confirmation_dialog/confirmation_dialog";
import { CopyButton } from "@web/core/copy_button/copy_button";
import { is24HourFormat } from "@web/core/l10n/time";
import { isHtmlEmpty } from "@web/core/utils/html";
import { useArchiveOrUnlinkCalendarEvent } from "@calendar/views/hooks";
import { useService } from "@web/core/utils/hooks";

export class AppointmentCalendarEventPopover extends Component {
    static template = "appointment.AppointmentCalendarEventPopover";
    static components = { CopyButton };
    props = useProps({
        close: t.function(),
        data: t.object(),
        reload: t.function(),
        resId: t.number(),
        resModel: t.string(),
    });

    setup() {
        super.setup(...arguments);
        this.action = useService("action");
        this.archiveOrUnlinkCalendarEvent = useArchiveOrUnlinkCalendarEvent();
        this.dialog = useService("dialog");
        this.formattedTime = this.props.data.start.toFormat(is24HourFormat() ? "HH:mm" : "hh:mm a");
        this.isHtmlEmpty = isHtmlEmpty;
        this.orm = useService("orm");
    }

    async onClickAppointmentStatus(status) {
        if (this.props.data.appointment_type_id) {
            await this.orm.write(this.props.resModel, [this.props.resId], { appointment_status: status });
            this.props.reload();
        }
    }

    deleteConfirmationDialogProps() {
        return {
            body: deleteConfirmationMessage,
            cancel: () => {},
            cancelLabel: _t("No, keep it"),
            confirm: async () => {
                await this.orm.unlink(this.props.resModel, [this.props.resId]);
                this.action.doAction("soft_reload");
            },
            confirmClass: "btn-danger",
            confirmLabel: _t("Delete"),
            title: _t("Bye-bye, record!"),
        };
    }

    async onClickDelete() {
        const { data } = this.props;
        await this.archiveOrUnlinkCalendarEvent({
            requestedAction: "unlink",
            resId: this.props.resId,
            partnerIds: data.partner_ids,
            recurrency: data.recurrency,
            start: data.start,
            defaultAction: () => this.dialog.add(ConfirmationDialog, this.deleteConfirmationDialogProps(data)),
        });
    }

    onClickEdit() {
        this.action.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "calendar.event",
                views: [[false, "form"]],
                res_id: this.props.resId,
            }
        );
    }

    getAppointmentStatusColorIndex(recordData) {
        const now = luxon.DateTime.now();
        return {
            attended: 10,
            booked: now.diff(recordData.start, ["minutes"]).minutes > 15 ? 2 : 4,
            no_show: 1,
            request: recordData.start < now ? 2 : 8,
        }[recordData.appointment_status];
    }

    getButtonClass(status) {
        let buttonClass = "btn-secondary";
        if (this.props.data.appointment_status === status) {
            buttonClass = `o_appointment_status_btn_color_${this.getAppointmentStatusColorIndex(this.props.data)}`;
        }
        return buttonClass;
    }
}
