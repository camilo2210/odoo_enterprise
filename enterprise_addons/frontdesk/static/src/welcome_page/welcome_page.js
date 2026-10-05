import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { Component, onWillUnmount, onMounted, proxy, signal, t, useProps } from "@odoo/owl";
import { HostManualSelection } from "@frontdesk/host_page/host_manual_selection";

const { DateTime } = luxon;

export class WelcomePage extends Component {
    static template = "frontdesk.WelcomePage";
    static components = { HostManualSelection };

    props = useProps({
        companyName: t.string(),
        currentLang: t.string(),
        langs: t.or([t.object(), t.boolean()]),
        onChangeLang: t.function(),
        token: t.string(),
        resetData: t.function(),
        showScreen: t.function(),
        stationInfo: t.object(),
        currentComponent: t.string(),
        isMobile: t.boolean(),
        setVisitorData: t.function(),
        setHostData: t.function(),
        visitorData: t.or([t.object(), t.boolean()]),
        theme: t.string(),
        getVisitorData: t.function(),
    });

    inputNameRef = signal.ref();
    inputPhoneRef = signal.ref();
    inputEmailRef = signal.ref();
    inputCompanyRef = signal.ref();
    visitorFormRef = signal.ref();

    setup() {
        this.props.resetData();
        this.visitorData = this.props.getVisitorData() || false;
        onMounted(() => {
            this.inputNameRef()?.focus();
        });
        this.state = proxy({
            today: this.getCurrentTime(),
            qrCode: false,
            showManualSelection: false,
            hostName: "",
            hostAvatar: "",
        });
        this.timeInterval = setInterval(() => (this.state.today = this.getCurrentTime()), 1000);
        // Make the qr code only when self_check_in field is true from backend.
        if (this.props.stationInfo.self_check_in) {
            this._getQrCodeData();
            this.qrCodeInterval = setInterval(() => this._getQrCodeData(), 3600000); // 1 hour
        }
        onWillUnmount(() => {
            clearInterval(this.timeInterval);
            if (this.props.stationInfo.self_check_in) {
                clearInterval(this.qrCodeInterval);
            }
        });
    }

    getCurrentTime() {
        return DateTime.now().toLocaleString(DateTime.TIME_SIMPLE);
    }

    /**
     * @private
     */
    async _getQrCodeData() {
        const response = await rpc(
            `/kiosk/${this.props.stationInfo.id}/get_tmp_code/${this.props.token}`
        );
        const token = encodeURIComponent(response[0] + response[1]);
        const lang = encodeURIComponent(this.props.currentLang);
        this.state.qrCode = this._makeQrCodeData(
            `${window.location.origin}/kiosk/${this.props.stationInfo.id}/mobile/${token}?lang=${lang}`
        );
    }

    /**
     * @private
     */
    _makeQrCodeData(url) {
        const codeWriter = new window.ZXing.BrowserQRCodeSvgWriter();
        const qrCodeSVG = new XMLSerializer().serializeToString(codeWriter.write(url, 500, 500));
        return "data:image/svg+xml;base64," + window.btoa(qrCodeSVG);
    }

    _saveVisitorData() {
        this.props.setVisitorData(
            this.inputNameRef().value,
            this.inputPhoneRef()?.value || false,
            this.inputEmailRef()?.value || false,
            this.inputCompanyRef()?.value || false
        );
        this.visitorData = this.props.getVisitorData();
    }

    _onConfirm() {
        const form = this.visitorFormRef();
        if (!form.checkValidity()) {
            form.reportValidity();
            return;
        }
        this._saveVisitorData();
        if (this.props.stationInfo.host_selection) {
            this.props.setHostData(this.host);
        }

        this.props.showScreen("RegisterPage");
    }
    selectedHost(host) {
        this.host = host;
        this.state.hostName = host?.display_name ?? "";
        this.state.hostAvatar = host?.avatar ?? "";
        this.state.showManualSelection = false;
    }

    showManualSelection() {
        this._saveVisitorData();
        this.state.showManualSelection = true;
    }

    goBackFromManualSelection() {
        this.state.showManualSelection = false;
    }

    changePrivacySettingVisibility() {
        var privacyDetails = document.getElementsByName("privacy_details_div").item(0);
        if (privacyDetails.style.display == "flex") {
            privacyDetails.style.display = "none";
        } else if (privacyDetails.style.display == "none") {
            privacyDetails.style.display = "flex";
        }
    }
}

registry.category("frontdesk_screens").add("WelcomePage", WelcomePage);
