export function hasOrderCard({
    orderNumber,
    productName,
    quantity,
    cancelledQty,
    note,
    comboLine,
    pending,
}) {
    let trigger = `.o_pdis_order_card`;
    if (orderNumber) {
        trigger += `:has(.o_pdis_tracking_number:contains("${orderNumber}"))`;
    }
    if (productName) {
        trigger += `:has(.o_pdis_product-name:contains("${productName}"))`;
    }
    if (quantity) {
        quantity = parseFloat(quantity) % 1 === 0 ? parseInt(quantity).toString() : quantity;
        trigger += `:has(.o_pdis_todo:contains("${quantity}x"))`;
    }
    if (cancelledQty) {
        cancelledQty =
            parseFloat(cancelledQty) % 1 === 0 ? parseInt(cancelledQty).toString() : cancelledQty;
        trigger += `:has(.o_pdis--cancelled:contains("${cancelledQty}x"))`;
    }
    if (note) {
        trigger += `:has(.o_tag_badge_text:contains("${note}"))`;
    }
    if (pending) {
        trigger += `:has(.text-bg-warning:contains("Pending"))`;
    }
    if (Array.isArray(comboLine)) {
        comboLine.forEach((line) => {
            trigger += `:has(.o_preparation_display_orderline.ms-4 .o_pdis_product-name:contains("${line}"))`;
        });
    } else if (comboLine) {
        trigger += `:has(.o_preparation_display_orderline.ms-4 .o_pdis_product-name:contains("${comboLine}"))`;
    }
    const args = JSON.stringify(arguments[0]);
    return [
        {
            content: `Check order card with attributes: ${args}`,
            trigger,
        },
    ];
}

export function setStage(stageName) {
    return [
        {
            content: `change stage '${stageName}'`,
            trigger: `.o_pdis_navbar_stage:contains("${stageName}")`,
            run: "click",
        },
        {
            content: `Current stage '${stageName}'`,
            trigger: `.o_pdis_navbar_stage.selected:contains("${stageName}")`,
        },
    ];
}

export function clickOrder(orderNumber) {
    return [
        {
            content: `Click on order with number: ${orderNumber}`,
            trigger: `.o_pdis_order_card_header:has(.o_pdis_tracking_number:contains("${orderNumber}")`,
            run: "click",
        },
    ];
}

export function clickOrderline(orderNumber, productName) {
    return [
        {
            content: `Click on orderline with order number: ${orderNumber} and product name ${productName}`,
            trigger: `.o_pdis_order_card:has(.o_pdis_tracking_number:contains("${orderNumber}")) .o_preparation_display_orderline:has(.o_pdis_product-name:contains("${productName}"))`,
            run: "click",
        },
    ];
}

export function isStrickedOrderline(orderNumber, productName) {
    return [
        {
            content: `Check if orderline stricked with order number: ${orderNumber} and product name ${productName}`,
            trigger: `.o_pdis_order_card:has(.o_pdis_tracking_number:contains("${orderNumber}")) .o_preparation_display_orderline:contains("${productName}").text-decoration-line-through`,
        },
    ];
}

export function clickRecall() {
    return [
        {
            content: "Click on the Recall button",
            trigger: `.btn.btn-light:contains("Recall")`,
            run: "click",
        },
    ];
}

export function clearFilterButton() {
    return [
        {
            content: "Click on the Clear Filter button",
            trigger: `.o_pdis_sidebar .btn.btn-lg:contains("Clear All Filter")`,
            run: "click",
        },
    ];
}

export function clickFilterButton() {
    return [
        {
            content: "Click on the Filter button",
            trigger: `.btn.border.p-2.fs-5.rounded`,
            run: "click",
        },
    ];
}

export function checkOrderCardCount(n) {
    return {
        content: `Check that there is ${n} order cards displayed`,
        trigger: `.o_pdis_orders:has(.o_pdis_order_card:count(${n}))`,
    };
}

export function clickFilterName(name) {
    return {
        trigger: `.o_pdis_sidebar span:contains("${name}")`,
        run: "click",
    };
}
