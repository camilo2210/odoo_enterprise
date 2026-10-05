import { OboxScale } from "@obox_point_of_sale/app/utils/scale/obox_scale";
import { beforeEach, expect, test } from "@odoo/hoot";
import { allowTranslations } from "@web/../tests/web_test_helpers";

beforeEach(allowTranslations);

const makeScale = (oboxValues) =>
    new OboxScale({ config: { obox_scale_id: { identifier: "scale", obox_id: oboxValues } } });

test("address uses the obox local_address, port included", () => {
    const scale = makeScale({ local_ip: "192.168.1.100", local_address: "192.168.1.100:8080" });
    expect(scale.address).toBe("http://192.168.1.100:8080");
});

test("address falls back to the obox local_ip without a local_address", () => {
    expect(makeScale({ local_ip: "192.168.1.100" }).address).toBe("http://192.168.1.100");
});
