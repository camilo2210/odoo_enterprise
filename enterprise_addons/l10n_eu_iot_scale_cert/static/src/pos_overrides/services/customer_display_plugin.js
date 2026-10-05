import { patch } from "@web/core/utils/patch";
import { CustomerDisplayTerminalPlugin } from "@point_of_sale/app/plugins/customer_display_terminal_plugin";

patch(CustomerDisplayTerminalPlugin.prototype, {
    _buildDisplayPayload(order) {
        const orderData = super._buildDisplayPayload(order);
        orderData.lines = orderData.lines.map((lineData, index) => {
            const lineRecord = order.lines[index];
            const result = {
                ...lineData,
                showUnit: lineRecord.product_id.uom_id?.id !== lineRecord.config._unit_uom_id,
            };
            if (lineRecord.uiState.isDeleted) {
                result.qty = lineRecord.uiState.deletedWeightQuantityStr.qtyStr;
                result.price = lineRecord.uiState.deletedWeightPriceStr;
                result.strikethrough = true;
            }
            return result;
        });
        return orderData;
    },
});
