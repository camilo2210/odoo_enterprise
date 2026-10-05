import { _t } from "@web/core/l10n/translation";

import { AccountReportController } from "@account_reports/components/account_report/controller";
import { AccountReportFilters } from "@account_reports/components/account_report/filters/filters";

export class L10nPhBoaFalReportFilters extends AccountReportFilters {
    static template = "l10n_ph_reports_asset.FalReportFilters";

    get assetStatusHeader() {
        return this._getHeader(_t("Asset Status"), "asset_states");
    }

    _getHeader(label, key) {
        const options = this.controller.options()[key] || [];
        const items = options.filter((o) => o.model === 'account.asset.group' || o.model === undefined);
        const selected = items.filter((o) => o.selected);
        if (selected.length === 0) return `${_t("All")} ${label}`;
        const names = selected.map((o) => o.name);
        return names.length <= 5 ? names.join(", ") : `${names.slice(0, 5).join(", ")}... (+${names.length - 5})`;
    }

    toggleStatus(state) {
        this._toggleOption("asset_states", state);
    }

    selectAssetGroup(group) {
        this._toggleOption("asset_groups", group);
    }

    _toggleOption(optionKey, item) {
        item.selected = !item.selected;
        const options = this.controller.options()[optionKey];
        const selectableItems = options.filter(o => o.model === 'account.asset.group' || o.model === undefined);
        const selectedCount = selectableItems.filter(o => o.selected).length;
        if (selectedCount === selectableItems.length) {
            selectableItems.forEach(o => o.selected = false);
        }
        this.applyFilters(optionKey);
    }

    unfoldCompanyAssetGroups(selectedDivider) {
        let inSection = false;
        // Use cachedFilterOptions to update the UI instantly without server round-trip
        for (const item of this.controller.cachedFilterOptions().asset_groups) {
            if (item.id === "divider" && item.model === "res.company" && item.name === selectedDivider.name) {
                item.unfolded = !item.unfolded;
                inSection = true;
                continue;
            }
            if (inSection && item.id === "divider") break;
            if (inSection) item.visible = !item.visible;
        }
    }
}

AccountReportController.registerCustomComponent(L10nPhBoaFalReportFilters);
