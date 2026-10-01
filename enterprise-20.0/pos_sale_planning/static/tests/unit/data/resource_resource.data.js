import { patch } from "@web/core/utils/patch";
import { ResourceResource } from "@pos_planning/../tests/unit/data/resource_resource.data";

patch(ResourceResource.prototype, {
    _load_pos_data_fields() {
        return [...super._load_pos_data_fields(), "name"];
    },
});

ResourceResource._records = [
    ...ResourceResource._records,
    { id: 10, name: "Meeting Room A", resource_type: "material" },
    { id: 11, name: "Conference Room B", resource_type: "material" },
    { id: 12, name: "Training Room C", resource_type: "material" },
];
