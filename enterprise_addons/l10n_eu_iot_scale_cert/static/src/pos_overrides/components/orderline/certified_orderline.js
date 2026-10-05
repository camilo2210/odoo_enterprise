import { patch } from "@web/core/utils/patch";
import { Orderline } from "@point_of_sale/app/components/orderline/orderline";

patch(Orderline.prototype, {
    get lineScreenValues() {
        const result = super.lineScreenValues;
        const unitOfMeasure = this.line.product_id?.uom_id;
        if (unitOfMeasure && unitOfMeasure.id !== this.line.config._unit_uom_id) {
            result.decimalPart += `\xa0${unitOfMeasure.name}`;
            result.displayPriceUnit = `${this.line.currencyDisplayPriceUnit} / ${unitOfMeasure.name}`;
        }
        if (this.line.uiState.deletedWeightPriceStr) {
            result.price = this.line.uiState.deletedWeightPriceStr;
        }
        return result;
    },

    get lineClasses() {
        return (
            super.lineClasses + (this.line.uiState.isDeleted ? " text-decoration-line-through" : "")
        );
    },
});
