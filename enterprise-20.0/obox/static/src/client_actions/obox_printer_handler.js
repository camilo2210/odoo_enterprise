import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

registry.category("printer.type.handlers").add("obox", async (printer, _duplex, jobs, services) => {
    const { orm, notification } = services;
    for (const job of jobs.filter((job) => job.type === "obox")) {
        await orm.call("printer.printer", "obox_print", [printer.id, job.report]);
        notification.add(_t("Started printing operation on printer %s...", printer.name), {
            type: "success",
        });
    }
});
