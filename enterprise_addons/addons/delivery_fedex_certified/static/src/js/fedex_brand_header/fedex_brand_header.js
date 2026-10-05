/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

/**
 * FedEx brand header — Unified Logo + service-marks disclaimer.
 *
 * Per the FedEx Integrator Additional Guidance (§3.b "FedEx Marks and Logos"
 * and §3.c "Disclaimer Statement"), this block must appear on every screen
 * where FedEx logos / trademarks / service marks / product names are present.
 *
 * Usage in any form/wizard view:
 *     <widget name="fedex_brand_header"/>
 */
export class FedexBrandHeader extends Component {
    static template = "delivery_fedex_certified.FedexBrandHeader";
}

registry.category("view_widgets").add("fedex_brand_header", {
    component: FedexBrandHeader,
});
