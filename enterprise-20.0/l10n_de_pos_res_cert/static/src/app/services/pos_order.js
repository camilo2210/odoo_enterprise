import { patch } from "@web/core/utils/patch";
import { PosOrder } from "@point_of_sale/app/models/pos_order";

patch(PosOrder.prototype, {
    initState() {
        super.initState();
        if (this.isCountryGermanyAndFiskaly() && this.config.module_pos_restaurant) {
            this.uiState = {
                ...this.uiState,
                tx_revision: this.uiState.tx_revision || 1,
                l10n_de_fiskaly_order_tx_uuid: this.uiState.l10n_de_fiskaly_order_tx_uuid || false,
            };
        }
    },
    dataMaker(prepOrPosLine, quantity, opts = {}) {
        const lineData = super.dataMaker(...arguments);
        if (this.isCountryGermanyAndFiskaly() && this.config.module_pos_restaurant) {
            const line = prepOrPosLine.pos_order_line_id || prepOrPosLine;
            lineData.data.price_unit = line.price_unit;
        }
        return lineData;
    },
});
