import { addSpreadsheetActionLazyLoader } from "@spreadsheet/assets_backend/spreadsheet_action_loader";
import { _t } from "@web/core/l10n/translation";

addSpreadsheetActionLazyLoader(
    "action_open_working_file_sheet",
    "working_file_sheet",
    _t("Working File Sheet")
);
