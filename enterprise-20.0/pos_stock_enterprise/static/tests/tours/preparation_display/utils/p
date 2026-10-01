import * as PrepDisplay from "@pos_enterprise/../tests/tours/preparation_display/utils/preparation_display_util";

export function hasStockOrderCard({
    orderNumber,
    productName,
    quantity,
    cancelledQty,
    note,
    comboLine,
    lotSerialNumber,
}) {
    let trigger = PrepDisplay.hasOrderCard({
        orderNumber,
        productName,
        quantity,
        cancelledQty,
        note,
        comboLine,
    })[0]["trigger"];
    if (Array.isArray(lotSerialNumber)) {
        lotSerialNumber.forEach((lot) => {
            trigger += `:has(.o_pdis_lot_serial_number:contains("${lot}"))`;
        });
    } else if (lotSerialNumber) {
        trigger += `:has(.o_pdis_lot_serial_number:contains("${lotSerialNumber}"))`;
    }
    const args = JSON.stringify(arguments[0]);
    return [
        {
            content: `Check order card with attributes: ${args}`,
            trigger,
        },
    ];
}
