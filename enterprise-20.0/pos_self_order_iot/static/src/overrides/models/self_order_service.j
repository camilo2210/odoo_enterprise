import { SelfOrder, selfOrderService } from "@pos_self_order/app/services/self_order_service";
import { patch } from "@web/core/utils/patch";

patch(selfOrderService, {
    dependencies: [...selfOrderService.dependencies, "iot_http"],
});

patch(SelfOrder.prototype, {
    async setup(env, services) {
        this.iotHttp = services.iot_http;
        await super.setup(...arguments);

        this.iotHttp.cacheIotBoxRecords(this.models["iot.box"].getAll());
        if (this.config.self_ordering_mode === "mobile") {
            this.iotHttp.disableLocalNetwork();
        }
    },
    shouldUpdateLastOrderChange() {
        const preparationPrinterTypes = this.config.preparation_printer_ids.map(
            (printer) => printer.printer_type
        );
        if (
            this.config.self_ordering_mode === "mobile" &&
            preparationPrinterTypes.includes("iot")
        ) {
            // The last order change should not be updated in this case,
            // because the POS will print the prep order when the payment succeeds
            return false;
        }
        return super.shouldUpdateLastOrderChange();
    },
});
