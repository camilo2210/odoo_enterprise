import { PosDataPlugin } from "@point_of_sale/app/plugins/pos_data_plugin";
import { patch } from "@web/core/utils/patch";
import { registerPythonTemplate } from "@point_of_sale/app/utils/convert_python_template";

export const unpatchPrepDataPlugin = patch(PosDataPlugin.prototype, {
    async loadInitialData() {
        const pdisId = odoo.preparation_display.id;
        const data = await this.orm.call("pos.prep.display", "load_preparation_data", [
            parseInt(pdisId),
        ]);
        // The model registry is built only once. Consumers keep a reference to it
        // (and to the records themselves), so a reload must update the existing
        // records in place instead of recreating the whole registry.
        if (!this.models) {
            this.initFieldsAndRelations(this.getFieldsAndRelations(data));
        }
        for (const template of data["ir.ui.view"]["records"]) {
            if (template._template) {
                registerPythonTemplate(template.key, "", template._template);
            }
        }
        return Object.fromEntries(Object.entries(data).map(([key, value]) => [key, value.records]));
    },
    async initData(hard = false, limit = true) {
        const data = await this.loadInitialData(hard, limit);

        this.models.loadConnectedData(data, []);
    },
    async initializeDeviceIdentifier() {
        return false;
    },
    initializeWebsocket() {
        return false;
    },
    initIndexedDB() {
        return false;
    },
    initListeners() {
        return false;
    },
    synchronizeLocalDataInIndexedDB() {
        return true;
    },
    async getCachedServerDataFromIndexedDB() {
        return {};
    },
    async getLocalDataFromIndexedDB() {
        return {};
    },
    async missingRecursive(recordMap) {
        return recordMap;
    },
    async deleteRecordsInIndexedDB(model, ids) {
        return true;
    },
});
