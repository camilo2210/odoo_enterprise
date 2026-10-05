import { _t } from "@web/core/l10n/translation";
import { Plugin } from "@html_editor/plugin";
import { MAIN_PLUGINS } from "@html_editor/plugin_sets";
import { FormViewDialog, formViewDialogProps } from "@web/views/view_dialogs/form_view_dialog";
import { useProps, t } from "@odoo/owl";
import { isLinkSupported } from "@html_editor/main/link/link_plugin";

class AppointmentFormViewDialog extends FormViewDialog {
    props = useProps({
        ...formViewDialogProps,
        insertLink: t.function(),
    });
    setup() {
        super.setup();
        this.viewProps.insertLink = this.props.insertLink;
        this.viewProps.closeDialog = this.props.close;
    }
}

class AppointmentPlugin extends Plugin {
    static id = "appointment";
    static dependencies = ["selection", "link", "dialog"];
    resources = {
        user_commands: [
            {
                id: "insertAppointment",
                title: _t("Appointment"),
                description: _t("Add a specific appointment"),
                icon: "calendar_today",
                iconClass: "oi-filled",
                run: this.addAppointment.bind(this),
                isAvailable: isLinkSupported,
            },
        ],
        powerbox_items: [
            {
                categoryId: "navigation",
                commandId: "insertAppointment",
            },
        ],
    };

    addAppointment() {
        this.dependencies.dialog.addDialog(AppointmentFormViewDialog, {
            resModel: "appointment.invite",
            context: {
                form_view_ref: "appointment.appointment_invite_view_form_insert_link",
                default_appointment_type_ids: [],
                default_staff_user_ids: [],
            },
            size: "md",
            title: _t("Insert Appointment Link"),
            insertLink: (url) =>
                this.dependencies.link.insertLink(url, _t("Schedule an Appointment")),
        });
    }
}

// add appointment plugin for all standard use cases
MAIN_PLUGINS.push(AppointmentPlugin);
