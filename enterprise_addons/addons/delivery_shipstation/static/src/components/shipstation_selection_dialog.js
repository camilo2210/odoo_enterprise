/** @odoo-module */

import { Component, proxy, t, useProps } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class CarrierSelectorDialog extends Component {
    static template = "delivery_shipstation.CarrierSelector";
    static components = { Dialog };

    props = useProps({
        carrier_record_id: t.number(),
        carriers: t.array().optional(),
        current_carrier_id: t.or([t.string(), t.literal(false)]).optional(),
        current_service_code: t.or([t.string(), t.literal(false)]).optional(),
        close: t.function(),
    });

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.uiService = useService("ui");

        this.recordId = this.props.carrier_record_id;

        const carriers = this.props.carriers || [];
        const selectedCarrier = this.props.current_carrier_id
            ? carriers.find((c) => c.carrier_id === this.props.current_carrier_id)
            : undefined;
        const selectedService = selectedCarrier && this.props.current_service_code
            ? selectedCarrier.services.find(
                (s) => s.service_code === this.props.current_service_code
            )
            : undefined;

        const initialStep = selectedCarrier && this.isSmall ? 2 : 1;

        this.state = proxy({
            carriers,
            selectedCarrier,
            selectedService,
            step: initialStep,
        });
    }

    get isSmall() {
        return this.uiService.isSmall;
    }

    get dialogTitle() {
        if (this.isSmall) {
            return this.state.step === 1 ? _t("Select Carrier") : _t("Select Service");
        }
        return _t("ShipStation Carrier Selector");
    }

    get services() {
        return this.state.selectedCarrier?.services || [];
    }

    get canSave() {
        return !!this.state.selectedService;
    }

    selectCarrier(carrier) {
        if (this.state.selectedCarrier !== carrier) {
            this.state.selectedCarrier = carrier;
            this.state.selectedService = null;
        }
        if (this.isSmall) {
            this.state.step = 2;
        }
    }

    selectService(service) {
        this.state.selectedService = service;
    }

    goBack() {
        this.state.step = 1;
        this.state.selectedService = null;
    }

    close() {
        this.props.close();
    }

    async save() {
        if (!this.state.selectedCarrier || !this.state.selectedService) {
            this.notification.add(_t("Please select a service"), { type: "danger" });
            return;
        }

        const friendlyServiceName = `${this.state.selectedCarrier.friendly_name} - ${this.state.selectedService.name}`;
        try {
            await this.orm.call("delivery.carrier", "update_shipstation_config", [
                [this.recordId],
                this.state.selectedCarrier.carrier_id,
                this.state.selectedService.service_code,
                friendlyServiceName,
                this.state.selectedCarrier.packages,
                this.state.selectedService.is_multi_package_supported || false,
                this.state.selectedService.is_return_supported || false,
            ]);
        } catch (error) {
            this.notification.add(error.data?.message || error.message || _t("Failed to save."), { type: "danger" });
            return;
        }

        this.notification.add(_t("Saved"), { type: "success" });
        this.props.close();
        this.actionService.doAction({ type: "ir.actions.client", tag: "soft_reload" });
    }
}

registry.category("actions").add("shipstation_carrier_selector", (env, action) => {
    const params = action.params || {};
    env.services.dialog.add(CarrierSelectorDialog, params);
});
