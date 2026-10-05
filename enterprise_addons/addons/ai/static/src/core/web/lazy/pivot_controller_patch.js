import { PivotController } from "@web/views/pivot/pivot_controller";
import { patch } from "@web/core/utils/patch";
import { useBus } from "@web/core/utils/hooks";
import { PivotModel } from "@web/views/pivot/pivot_model";
import { computeReportMeasures } from "@web/views/utils";

patch(PivotController.prototype, {
    setup() {
        super.setup(...arguments);
        useBus(this.env.bus, "APPLY_AI_ADJUST_MODEL", async ({ detail }) => {
            const { measures } = detail;
            if (this.model instanceof PivotModel) {
                // Wait for any ongoing model load to avoid overwriting its metadata.
                await this.model.race.getCurrentProm();
                const metaData = this.model._buildMetaData();
                const metaDataMeasures = computeReportMeasures(
                    metaData.fields,
                    metaData.fieldAttrs,
                    [...(metaData.activeMeasures || [])]
                );
                const validMeasures = measures.filter((m) => m in metaDataMeasures);
                const activeMeasures = metaData.activeMeasures || [];
                const measuresToToggle = new Set([
                    ...validMeasures.filter((m) => !activeMeasures.includes(m)), // measures to activate
                    ...(validMeasures.length
                        ? activeMeasures.filter((m) => !validMeasures.includes(m))
                        : []), // measures to deactivate
                ]);
                for (const measure of measuresToToggle) {
                    await this.model.toggleMeasure(measure);
                }
            }
        });
    },
});
