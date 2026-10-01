import { Component, t, useProps } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class ProductImageDialog extends Component {
    static components = { Dialog };
    static template = "stock_barcode.ProductImageDialog";

    props = useProps({
        record: t.object(),
        close: t.function(),
    });

    setup() {
        this.source = `/web/image/product.product/${this.props.record.id}/image_1024`;
        this.title = this.props.record.display_name;
    }
}
