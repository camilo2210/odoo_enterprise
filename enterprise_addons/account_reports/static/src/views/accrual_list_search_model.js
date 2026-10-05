import { AccrualPlugin } from "@account_reports/views/accrual_plugin";
import { providePlugins, usePlugin } from "@odoo/owl";
import { serializeDate } from "@web/core/l10n/dates";
import { SearchModel } from "@web/search/search_model";

const { DateTime } = luxon;


export class AccrualListSearchModel extends SearchModel {
    setup(services) {
        super.setup(services);
        providePlugins([AccrualPlugin]);
        this.accrual = usePlugin(AccrualPlugin);
    }

    exportState() {
        return {
            ...super.exportState(),
            ...this.accrual.exportState(),
        };
    }

    _importState(state) {
        super._importState(state);
        this.accrual.importState(state);
    }

    async load(config) {
        await super.load(config);
        this.accrual.entryDate ||= serializeDate(DateTime.now());
    }

    _getContext() {
        return Object.assign(super._getContext(), this.accrual.toContext());
    }
}
