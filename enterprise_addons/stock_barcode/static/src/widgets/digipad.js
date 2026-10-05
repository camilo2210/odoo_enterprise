import { registry } from "@web/core/registry";
import { useRecordObserver } from "@web/model/relational_model/utils";
import { formatFloat } from "@web/core/utils/numbers";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, proxy, t, useProps } from "@odoo/owl";

export class Digipad extends Component {
    static template = "stock_barcode.DigipadTemplate";

    props = useProps({
        ...standardWidgetProps,
        fieldToEdit: t.string(),
        fulfilledAt: t.string().optional(),
    });

    setup() {
        this.orm = useService("orm");
        const { data } = this.props.record;
        const context = this.props.record.evalContext.context;
        this.quantity = data[this.props.fieldToEdit];
        this.value = String(this.quantity);
        this.fulfillQuantity =
            this.props.fulfilledAt && !context.hide_qty_to_count ? data[this.props.fulfilledAt] : 0;
        if (context.force_fullfil_quantity) {
            this.fulfillQuantity = context.force_fullfil_quantity;
        }
        const field = this.props.record.model.config.fields[this.props.fieldToEdit];
        this.precision = field.digits[1];
        this.productId = this.props.record.data.product_id.id;
        this.state = proxy({
            packagingButtons: [],
        });
        useRecordObserver(async (record) => {
            if (this.productId != record.data.product_id.id) {
                this.productId = record.data.product_id.id;
                await this._fetchPackagingButtons();
            }
        });
        onWillStart(async () => {
            this.displayUOM = await user.hasGroup("uom.group_uom");
            await this._fetchPackagingButtons();
        });
    }

    get changes() {
        return { [this.props.fieldToEdit]: Number(this.value) };
    }

    get quantityToFulfill() {
        if (!this.fulfillQuantity) {
            return 0;
        }
        const record = this.props.record.data;
        const currentQty = record[this.props.fieldToEdit];

        const quantityToFulfill = this.fulfillQuantity - currentQty;
        const params = { digits: [false, this.precision], thousandsSep: "", decimalPoint: "." };
        return parseFloat(formatFloat(quantityToFulfill, params));
    }

    get buttonContainerClass() {
        return this.fulfillQuantity ? "col-3" : "col-4";
    }

    get buttonFulfillClass() {
        if (this.quantityToFulfill > 0) {
            return "btn-success";
        } else if (this.quantityToFulfill < 0) {
            return "btn-warning";
        }
        return "btn-secondary text-success";
    }

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Copies the input value if digipad value is not set yet, or overrides it if there is a
     * difference between the two values (in case user has manualy edited the input value).
     * @private
     */
    _checkInputValue() {
        const input = document.querySelector(`div[name="${this.props.fieldToEdit}"] input`);
        const inputValue = input.value;
        if (Number(this.value) != Number(inputValue)) {
            this.value = inputValue;
            this.quantity = Number(this.value || 0);
        }
    }

    /**
     * Increments the field value by the interval amount (1 by default).
     * @private
     * @param {integer} [interval=1]
     */
    async _increment(interval = 1, enforceQuantity = false) {
        if (enforceQuantity) {
            this.quantity = interval;
        } else {
            this._checkInputValue();
            this.quantity = Math.max(this.quantity + interval, 0);
        }
        this.value = this.quantity.toFixed(this.precision);
        if (parseFloat(this.value) % 1 == 0) {
            this.value = String(Math.floor(parseFloat(this.value)));
        }
        await this.props.record.update(this.changes);
    }

    /**
     * Search for the product's packaging buttons.
     * @private
     * @returns {Promise}
     */
    async _fetchPackagingButtons() {
        const record = this.props.record.data;
        this.productUom = false;
        if (record.uom_id) {
            this.productUom = (
                await this.orm.searchRead("uom.uom", [["id", "=", record.uom_id.id]], ["factor"])
            )?.[0];
        }
        if (record.product_id.id) {
            const productUoms = await this.orm.searchRead(
                "product.product",
                [["id", "=", record.product_id.id]],
                ["uom_ids", "extra_uom_ids"],
                { limit: 1 }
            );
            if (productUoms.length === 0) {
                return;
            }
            const allUomIds = [
                ...new Set([...productUoms[0].uom_ids, ...productUoms[0].extra_uom_ids]),
            ];
            const domain = [["id", "in", allUomIds]];
            if (this.quantityToFulfill) {
                // Doesn't fetch packaging with a too high quantity.
                domain.push(["factor", "<=", this.quantityToFulfill]);
            }
            this.state.packagingButtons = await this.orm.searchRead(
                "uom.uom",
                domain,
                ["name", "factor", "package_type_id"],
                { limit: 2 }
            );
        } else {
            this.state.packagingButtons = [];
        }
    }
    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Handles the click on one of the digipad's button and updates the value..
     * @private
     * @param {String} button
     */
    erase() {
        this._checkInputValue();
        this.quantity = 0;
        this.value = String(this.quantity);
        this.props.record.update(this.changes);
    }

    increment() {
        this._increment();
    }

    decrement() {
        this._increment(-1);
    }

    /**
     * Handles the click on one of the digipad's button and updates the value..
     * @private
     * @param {String} button
     */
    fulfill() {
        this._checkInputValue();
        this.quantity = this.fulfillQuantity;
        this.value = String(this.quantity);
        this.props.record.update(this.changes);
    }
}

export const digipad = {
    component: Digipad,
    extractProps: ({ attrs }) => ({
        fieldToEdit: attrs.field_to_edit,
        fulfilledAt: attrs.fulfilled_at,
    }),
};
registry.category("view_widgets").add("digipad", digipad);
