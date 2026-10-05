import { odooExceptionTitleMap, WarningDialog } from "@web/core/errors/error_dialogs";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

odooExceptionTitleMap.set(
    "odoo.addons.voip.models.phone_service_api.PhoneServiceError",
    _t("Odoo Phone Error")
);

registry
    .category("error_dialogs")
    .add("odoo.addons.voip.models.phone_service_api.PhoneServiceError", WarningDialog);
