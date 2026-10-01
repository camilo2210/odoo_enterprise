import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { uuid } from "@web/core/utils/strings";

export async function printIotJobs(
    { iot_id, identifier, name },
    duplex,
    jobs,
    { notification, iot_http }
) {
    for (const job of jobs) {
        await iot_http.action(
            iot_id,
            identifier,
            { document: job.report, duplex, print_id: uuid() },
            () => {
                notification.add(_t("Started printing operation on printer %s...", name), {
                    type: "success",
                });
            }
        );
    }
}

registry.category("printer.type.handlers").add("iot", async (printer, duplex, jobs, services) => {
    services.ui.block({ message: _t("Printing document(s) with IoT Box...") });
    const iotJobs = jobs.filter((job) => job.type === "iot");
    await printIotJobs(printer, duplex, iotJobs, services);
    services.ui.unblock();
});
