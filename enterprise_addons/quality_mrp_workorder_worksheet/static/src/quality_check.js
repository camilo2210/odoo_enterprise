import { patch } from "@web/core/utils/patch";
import { QualityCheck } from "@mrp_workorder/mrp_display/mrp_record_line/quality_check";

patch(QualityCheck.prototype, {
    get icon() {
        return this.type === "worksheet" ? "article" : super.icon;
    },
    get iconClass() {
        return this.type === "worksheet" ? "oi-filled" : "";
    },
    get passFailTypes() {
        return [...super.passFailTypes, "worksheet"];
    },
    clicked() {
        return this.type === "worksheet" ? this.doActionAndNext("action_open_quality_check_wizard", "none") : super.clicked();
    },
});
