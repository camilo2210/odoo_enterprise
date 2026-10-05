import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
/* global html2canvas */

import { Dialog } from "@web/core/dialog/dialog";
import { loadJS } from "@web/core/assets";
import { Component, onWillStart, useProps, proxy, signal, t } from "@odoo/owl";
import { localization } from "@web/core/l10n/localization";
import { NameAndSignature } from "@web/core/signature/name_and_signature";

export class SignNameAndSignature extends NameAndSignature {
    static template = "sign.NameAndSignature";
    // Inline copy of NameAndSignature's schema (no exported const in web)
    props = useProps({
        signature: t.object(),
        defaultFont: t.string().optional(""),
        displaySignatureRatio: t.number().optional(3.0),
        fontColor: t.string().optional("DarkBlue"),
        signatureType: t.string().optional("signature"),
        noInputName: t.boolean().optional(false),
        mode: t.string().optional(),
        activeFrame: t.boolean(),
        defaultFrame: t.string(),
        frame: t.object().optional(),
        hash: t.string(),
        onNameChange: t.function(),
        onSignatureChange: t.function().optional(() => () => {}),
    });

    signFrameRef = signal.ref();

    setup() {
        super.setup();
        this.props.signature.signatureChanged = this.state.signMode !== "draw";

        if (this.props.frame) {
            this.state.activeFrame = this.props.activeFrame || false;
            this.frame = this.props.defaultFrame;

            this.props.frame.updateFrame = () => {
                if (this.state.activeFrame) {
                    this.props.signature.signatureChanged = true;
                    const xOffset = localization.direction === "rtl" ? 0.75 : 0.06; // magic numbers
                    this.signFrameRef().classList.toggle("active", true);
                    return html2canvas(this.signFrameRef(), {
                        backgroundColor: null,
                        width: this.signatureRef().width,
                        height: this.signatureRef().height,
                        x: -this.signatureRef().width * xOffset,
                        y: -this.signatureRef().height * 0.09,
                    }).then((canvas) => {
                        this.frame = canvas.toDataURL("image/png");
                    });
                }
                return Promise.resolve(false);
            };

            this.props.frame.getFrameImageSrc = () => (this.state.activeFrame ? this.frame : false);
        }

        onWillStart(() => {
            if (this.props.frame) {
                return loadJS("/sign/static/lib/html2canvas.js");
            }
        });
    }

    onFrameChange() {
        this.state.activeFrame = !this.state.activeFrame;
    }

    onSignatureAreaClick() {
        if (this.state.signMode === "draw") {
            this.props.signature.signatureChanged = true;
            this.props.onSignatureChange(this.state.signMode);
        }
    }

    onClickSignLoad() {
        super.onClickSignLoad();
        this.props.signature.signatureChanged = true;
    }

    async onClickSignAuto() {
        if (this.fonts.length <= 1) {
            this.fonts = await rpc(`/web/sign/get_fonts/`);
        }
        super.onClickSignAuto();
        this.props.signature.signatureChanged = true;
    }

    onClickSignDrawClear() {
        super.onClickSignDrawClear();
        this.props.signature.signatureChanged = true;
    }

    get signFrameClass() {
        return this.state.activeFrame && this.state.signMode !== "draw" ? "active" : "";
    }

    /**
     * Override to enable/disable SignNameAndSignatureDialog's footer buttons
     * @param { Event } e
     */
    onInputSignName(e) {
        super.onInputSignName(e);
        this.props.onNameChange(this.props.signature.name);
        this.props.onSignatureChange(this.state.signMode);
    }
}

export class SignNameAndSignatureDialog extends Component {
    static template = "sign.SignNameAndSignatureDialog";
    static components = {
        Dialog,
        SignNameAndSignature,
    };

    props = useProps({
        signature: t.object(),
        frame: t.object().optional(),
        signatureType: t.string().optional(),
        displaySignatureRatio: t.number(),
        activeFrame: t.boolean(),
        defaultFrame: t.string().optional(),
        mode: t.string().optional(),
        signatureImage: t.string().optional(),
        hash: t.string(),
        onConfirm: t.function(),
        onConfirmAll: t.function().optional(),
        close: t.function(),
    });

    setup() {
        this.footerState = proxy({
            signButtonDisabled:
                !this.props.signature.name || !this.props.signature.signatureChanged,
            signAllButtonsDisabled: !this.props.signature.name,
        });
    }

    get nameAndSignatureProps() {
        return {
            signature: this.props.signature || "signature",
            signatureType: this.props.signatureType,
            displaySignatureRatio: this.props.displaySignatureRatio,
            activeFrame: this.props.activeFrame,
            defaultFrame: this.props.defaultFrame || "",
            mode: this.props.mode || "auto",
            frame: this.props.frame || false,
            hash: this.props.hash,
            onNameChange: this.onNameChange.bind(this),
            defaultFont: "LaBelleAurore-Regular.ttf",
            onSignatureChange: this.onSignatureChange.bind(this),
        };
    }

    get dialogProps() {
        return {
            title: _t("Adopt Your Signature"),
            size: "md",
        };
    }

    onNameChange(name) {
        const isNameFilled = Boolean(name);
        this.footerState.signButtonDisabled = !isNameFilled;
        this.footerState.signAllButtonsDisabled = !isNameFilled;
    }

    onSignatureChange(signMode) {
        const { name, isSignatureEmpty, signatureChanged } = this.props.signature;
        const isAutoMode = signMode === "auto";
        // Disable Sign all button if:
        // - Name is missing or empty
        //   - In "auto" mode, the name is only whitespace
        //   - In any other mode, the signature is empty
        const buttonsDisabled = !name || isAutoMode ? !name.trim() : isSignatureEmpty;
        if (this.footerState.signAllButtonsDisabled !== buttonsDisabled) {
            this.footerState.signAllButtonsDisabled = buttonsDisabled;
        }
        // Disable Sign button if:
        // - signature is not changed
        // - name is missing
        this.footerState.signButtonDisabled = buttonsDisabled || !signatureChanged;
    }
}
