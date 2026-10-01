import { onWillDestroy } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import {
    PhoneNumberRequiredListController,
    phoneNumberRequiredListView,
} from "../phone_number_required_list/phone_number_required_list_view";

export class DidNumberListController extends PhoneNumberRequiredListController {
    setup() {
        super.setup();
        this.busService = useService("bus_service");
        this.onDidNumberStatusUpdated = () => this.model.load();
        this.busService.subscribe("voip.did_number/status_updated", this.onDidNumberStatusUpdated);
        onWillDestroy(() => {
            this.busService.unsubscribe(
                "voip.did_number/status_updated",
                this.onDidNumberStatusUpdated
            );
        });
    }
}

export const didNumberListView = {
    ...phoneNumberRequiredListView,
    Controller: DidNumberListController,
};

registry.category("views").add("voip_did_number_list", didNumberListView);
