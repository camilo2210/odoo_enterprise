import { patch } from "@web/core/utils/patch";
import { getStrNotes } from "@point_of_sale/app/models/utils/order_change";
import { PosTicketPrinterPlugin } from "@point_of_sale/app/plugins/pos_ticket_printer_plugin";

patch(PosTicketPrinterPlugin.prototype, {
    getPreparationReceiptData(prepOrderLines) {
        const prepOrder = prepOrderLines[0].prep_order_id;
        const linesData = {
            addedQuantity: [],
            removedQuantity: [],
            noteUpdate: [],
            internal_note: getStrNotes(prepOrder.pdis_internal_note || false),
            general_customer_note: prepOrder.pdis_general_customer_note,
        };

        for (const line of prepOrderLines) {
            const remainingQty = line.todoQuantity;
            if (remainingQty <= 0) {
                continue;
            }
            const product = line.product_id;
            const posCategory = product.pos_categ_ids[0];
            linesData.addedQuantity.push({
                uuid: line.uuid,
                basic_name: line.order_id?.config_id.module_pos_restaurant
                    ? product.name
                    : product.display_name,
                product_id: product.id,
                attribute_value_names: (line.attribute_value_ids || []).map((a) => a.name),
                quantity: remainingQty,
                note: getStrNotes(line.internal_note),
                customer_note: line.customer_note || false,
                pos_categ_id: posCategory?.id || 0,
                pos_categ_sequence: posCategory?.sequence || 0,
                group: prepOrder.pos_course_id || false,
                isCombo: Boolean(line.combo_line_ids?.length),
                combo_parent_uuid: line.combo_parent_id?.uuid,
                combo_line_ids: line.combo_line_ids,
            });
        }
        return [linesData];
    },
    async printOrderChanges({ order, opts = {}, printers = this.config.preparation_printer_ids }) {
        if (opts.prepOrderLines) {
            opts.orderChange = this.getPreparationReceiptData(opts.prepOrderLines);
            opts.skipRetry = true;
        }
        return super.printOrderChanges({ order, opts, printers });
    },
});
