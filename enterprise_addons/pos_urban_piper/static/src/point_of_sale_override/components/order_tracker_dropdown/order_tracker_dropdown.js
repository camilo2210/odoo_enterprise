import { patch } from "@web/core/utils/patch";
import { OrderTrackerDropdown } from "@point_of_sale/app/components/order_tracker_dropdown/order_tracker_dropdown";

patch(OrderTrackerDropdown.prototype, {
    getOptions(type, state) {
        const options = super.getOptions(type, state);
        if (type === "DELIVERYPROVIDER") {
            return {
                ...options,
                upState: state,
            };
        }
        return options;
    },
    async handleToggle(aggregator) {
        await this.pos.data.write("urbanpiper.store.aggregator", [aggregator.id], {
            is_online: !aggregator.is_online,
        });
    },
    get externalOrderSummary() {
        if (this.pos.config.module_pos_urban_piper) {
            const deliveryOrderCount = this.pos.delivery_order_count;
            const aggregators = this.pos.config.urbanpiper_store_id.aggregator_lines.map(
                (aggregator) => {
                    const provider = aggregator.delivery_provider_id;
                    return {
                        type: "DELIVERYPROVIDER",
                        searchTerm: provider.name,
                        imageUrl: `/web/image?model=pos.delivery.provider&field=image_128&id=${provider.id}`,
                        new: deliveryOrderCount[provider.technical_name]?.awaiting || 0,
                        ongoing: deliveryOrderCount[provider.technical_name]?.preparing || 0,
                        done: deliveryOrderCount[provider.technical_name]?.done || 0,
                        onToggle: () => this.handleToggle(aggregator),
                        isChecked: aggregator.is_online,
                    };
                }
            );
            return [...super.externalOrderSummary, ...aggregators];
        }
        return super.externalOrderSummary;
    },
});
