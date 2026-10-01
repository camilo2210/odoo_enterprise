import { Plugin } from "@html_editor/plugin";
import { registry } from "@web/core/registry";
import { Cache } from "@web/core/utils/cache";
import { BuilderAction } from "@html_builder/core/builder_action";

export class AppointmentTypeOptionPlugin extends Plugin {
    static id = "AppointmentTypeOption";
    resources = {
        builder_actions: {
            AppointmentTypeShowAvatarsAction,
            AppointmentTypeShowAllowGuestsAction,
            AppointmentTypeShowDurationAction,
            AppointmentTypeShowTimezoneAction,
        },
    };
}

export class BaseAppointmentAction extends BuilderAction {
    setup(fieldName, applyValue, clearValue) {
        this.fieldName = fieldName;
        this.applyValue = applyValue;
        this.clearValue = clearValue;
        this.reload = {};
        this.appointmentTypeId = Number(this.document.documentElement.querySelector(".o_wappointment_type_options")?.dataset.appointmentTypeId);
        this.appointmentTypeCache = new Cache(this._fetchAppointmentType.bind(this), JSON.stringify);
    }
    async _fetchAppointmentType() {
        return (await this.services.orm.read(
            "appointment.type",
            [this.appointmentTypeId],
            ["allow_guests", "hide_duration", "hide_timezone", "show_avatars"]
        ))[0];
    }
    async set(apply) {
        await this.services.orm.write("appointment.type", [this.appointmentTypeId], {
            [this.fieldName]: apply ? this.applyValue : this.clearValue,
        });
    };
    async prepare() {
        this.appointmentType = await this.appointmentTypeCache.read();
    }
    isApplied() {
        return this.appointmentType[this.fieldName] === this.applyValue;
    }
    async load() {
        const wasApplied = this.appointmentType[this.fieldName] === this.applyValue;
        await this.set(!wasApplied);
    }
    apply() {}
    clear() {}
}

export class AppointmentTypeShowTimezoneAction extends BaseAppointmentAction {
    static id = "appointmentTypeShowTimezone";
    setup() {
        super.setup("hide_timezone", false, true);
    }
}

export class AppointmentTypeShowDurationAction extends BaseAppointmentAction {
    static id = "appointmentTypeShowDuration";
    setup() {
        super.setup("hide_duration", false, true);
    }
}

export class AppointmentTypeShowAvatarsAction extends BaseAppointmentAction {
    static id = "appointmentTypeShowAvatars";
    setup() {
        super.setup("show_avatars", true, false);
    }
}

export class AppointmentTypeShowAllowGuestsAction extends BaseAppointmentAction {
    static id = "appointmentTypeShowAllowGuests";
    setup() {
        super.setup("allow_guests", true, false);
    }
}

registry
    .category("website-plugins")
    .add(AppointmentTypeOptionPlugin.id, AppointmentTypeOptionPlugin);
