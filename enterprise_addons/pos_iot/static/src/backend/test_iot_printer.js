import { _t } from "@web/core/l10n/translation";
import { TestEPos } from "@point_of_sale/backend/test_epos/test_epos";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { initLNA } from "@point_of_sale/app/utils/init_lna";

patch(TestEPos.prototype, {
    setup() {
        this.iotHttpService = useService("iot_http");
        super.setup();
    },
    async getPrinterDataIOT(printer_id) {
        if (printer_id) {
            const response = await this.orm.read(
                "pos.printer",
                [printer_id],
                ["name", "printer_type", "iot_device_id", "use_lna"]
            );
            return response[0];
        } else {
            const data = this.props.record.data;
            return {
                id: this.props.record.resId || null,
                name: data.name,
                printer_type: data.printer_type,
                iot_device_id: data.iot_device_id,
                use_lna: data.use_lna,
            };
        }
    },
    async _printTo(printer_id = null) {
        const printer = await this.getPrinterDataIOT(printer_id);

        try {
            if (printer.printer_type !== "iot") {
                return super._printTo(...arguments);
            }
            const iotDeviceId = printer_id ? printer.iot_device_id[0] : printer.iot_device_id.id;
            const iot = await this.orm.searchRead(
                "iot.device",
                [["id", "=", iotDeviceId]],
                ["iot_id", "identifier"]
            );
            if (printer.use_lna) {
                await initLNA(this.notification);
            }

            this.iotHttpService.action(
                iot[0].iot_id[0],
                iot[0].identifier,
                {
                    action: "status",
                    printer_name: printer.name,
                },
                () =>
                    this.notification.add(_t("Test receipt printed"), {
                        type: "info",
                    }),
                () => {
                    this.notification.add(
                        _t("Failed to print the test receipt on the printer %s", printer.name),
                        { type: "danger" }
                    );
                }
            );
        } catch {
            this.notification.add(`${printer.name}: ${_t("Cannot reach IoT Box.")}`, {
                type: "danger",
            });
        }
    },
});
