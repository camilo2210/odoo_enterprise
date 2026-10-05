/** @odoo-module **/

import {Component, onMounted, signal, useProps} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class FedexEulaPdfField extends Component {

    static template = "delivery_fedex_certified.FedexEulaPdfField";
    static PDF_URL = "/delivery_fedex_certified/static/src/pdf/FedEx_EULA.pdf";
    props = useProps(standardFieldProps);


    setup() {
        this.iframeRef = signal.ref();
        onMounted(() => {
            this.setupViewer();
        });
    }

    get viewerUrl() {
        const pdf = encodeURIComponent(FedexEulaPdfField.PDF_URL);
        return `/web/static/lib/pdfjs/web/viewer.html` +
            `?file=${pdf}` +
            `#zoom=page-width&toolbar=0&navpanes=0&scrollbar=1`;
    }

    setupViewer() {
        this.iframeRef()?.addEventListener("load", () => {
            const doc = this.iframeRef()?.contentDocument;
            if (!doc) return;
            this.hidePdfToolbar(doc);
            this.setupScrollCheck(doc);
        });
    }

    hidePdfToolbar(doc) {
        const style = doc.createElement("style");
        style.textContent = `
            #toolbarContainer { display:none !important; }
            #sidebarContainer { display:none !important; }
            #secondaryToolbar { display:none !important; }
            #secondaryToolbarToggle { display:none !important; }
            #viewFind { display:none !important; }

            #outerContainer.sidebarOpen #mainContainer {
                left:0 !important;
            }

            #mainContainer {
                top:0 !important;
            }
        `;
        doc.head.appendChild(style);
    }

    setupScrollCheck(doc) {
        const container = doc.querySelector("#viewerContainer");
        if (!container) return;
        container.addEventListener("scroll", () => {
            const threshold = 20;
            const reached =
                container.scrollTop + container.clientHeight >=
                container.scrollHeight - threshold;
            if (reached && !this.props.record.data[this.props.name]) {
                this.props.record.update({ [this.props.name]: true });
            }
        });
    }
}

registry.category("fields").add("fedex_eula_pdf", {
    component: FedexEulaPdfField,
});
