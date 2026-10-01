import { registry } from "@web/core/registry";
import { Base } from "@point_of_sale/app/models/related_models";

export class PlatformOrderProvider extends Base {
    static pythonModel = "platform.order.provider";

    get imageUrl() {
        return `/web/image?model=${PlatformOrderProvider.pythonModel}&field=image_128&id=${this.id}&unique=${this.write_date}`;
    }
}

registry
    .category("pos_available_models")
    .add(PlatformOrderProvider.pythonModel, PlatformOrderProvider);
