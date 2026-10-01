import { Component, proxy, t, useProps } from "@odoo/owl";

export class BoxCluster extends Component {
    static template = "iap_extract.BoxCluster";

    props = useProps({
        cluster: t.object(),
        pageWidth: t.string(),
        pageHeight: t.string(),
        onClickBoxClusterCallback: t.function(),
    });

    state = proxy(this.props.cluster);

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    get style() {
        return [
            `left: calc(${this.state.boundingBox.midX} * ${this.props.pageWidth})`,
            `top: calc(${this.state.boundingBox.midY} * ${this.props.pageHeight})`,
            `width: calc(${this.state.boundingBox.width} * ${this.props.pageWidth})`,
            `height: calc(${this.state.boundingBox.height} * ${this.props.pageHeight})`,
            `transform: translate(-50%, -50%) rotate(${this.state.boundingBox.angle}deg)`,
            `-ms-transform: translate(-50%, -50%) rotate(${this.state.boundingBox.angle}deg)`,
            `-webkit-transform: translate(-50%, -50%) rotate(${this.state.boundingBox.angle}deg)`,
        ].join(";");
    }

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    onClickLabel() {
        this.props.onClickBoxClusterCallback(this.state.id, this.state.boundingBox.page);
    }
}
