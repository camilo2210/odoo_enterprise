import {
    ConfirmationDialog,
    confirmationDialogProps,
} from "@web/core/confirmation_dialog/confirmation_dialog";
import { registry } from "@web/core/registry";
import { usePopover } from "@web/core/popover/popover_hook";
import { useService, useAutofocus } from "@web/core/utils/hooks";
import { Component, useProps, onWillStart, signal, t } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

export class MrpLogTimeDialog extends ConfirmationDialog {
    static template = "mrp_workorder.MrpLogTimeDialog";
    props = useProps({
        ...confirmationDialogProps,
        employeeId: t.number(),
        workorderId: t.number(),
        stopWorking: t.function(),
    });
    static components = {
        ...ConfirmationDialog.components,
    };

    durationRef = signal.ref();
    durationStr = signal("0m0s");
    durationTip = signal("0m0s");

    setup() {
        super.setup();
        this.formatOptions = { showSeconds: true, unit: "minutes" };
        this.formatFloatTime = registry.category("formatters").get("float_time");
        this.parser = registry.category("parsers").get("float_time");
        this.resultPopover = usePopover(MrpLogTimePopover, { position: "bottom" });
        this.isInputValid = true;
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.orm = useService("orm");

        onWillStart(async () => {
            const [closedDuration, openedDuration] = await this.orm.call(
                "mrp.workorder",
                "get_employee_duration",
                [this.props.workorderId, this.props.employeeId]
            );
            this.ongoingTimer = openedDuration !== false;
            this.durationStr.set(
                this.formatFloatTime(closedDuration + openedDuration, this.formatOptions)
            );
            this.durationTip.set(this.durationStr());
        });

        useAutofocus({ ref: this.durationRef, selectAll: true });
    }

    parseFloatTime(str) {
        try {
            const duration = this.parser(str, "minutes");
            this.isInputValid = true;
            return duration < 0.0 ? 0.0 : duration;
        } catch {
            this.isInputValid = false;
            return 0.0;
        }
    }

    prettifyTimeString(str) {
        const duration = this.parseFloatTime(str);
        return this.formatFloatTime(duration, this.formatOptions);
    }

    onValueChange() {
        this.durationTip.set(this.prettifyTimeString(this.durationStr()));
        if (!this.isInputValid && this.resultPopover.isOpen) {
            this.closePopover();
        } else if (this.isInputValid && !this.resultPopover.isOpen) {
            this.openPopover();
        }
    }

    openPopover() {
        this.durationTip.set(this.prettifyTimeString(this.durationStr()));
        if (this.isInputValid) {
            this.durationRef().classList.remove("o_field_invalid");
            this.resultPopover.open(this.durationRef(), { signal: this.durationTip });
        }
    }

    closePopover() {
        this.resultPopover.close();
        if (this.isInputValid) {
            this.durationStr.set(this.durationTip());
        } else {
            this.durationRef().classList.add("o_field_invalid");
        }
    }

    async validate() {
        const duration = this.parseFloatTime(this.durationStr());
        if (!this.isInputValid) {
            this.notification.add(_t("Invalid duration"));
            return;
        }
        if (this.ongoingTimer) {
            await this.props.stopWorking();
        }
        await this.orm.call("mrp.workorder", "set_employee_duration", [
            this.props.workorderId,
            this.props.employeeId,
            duration,
        ]);
        this.props.close();
        this.notification.add(_t("The employee time log has been successfully updated"), {
            type: "success",
        });
    }
}

class MrpLogTimePopover extends Component {
    static template = "mrp_workorder.MrpLogTimePopover";
    props = useProps({
        signal: t.signal().optional(),
    });
}
