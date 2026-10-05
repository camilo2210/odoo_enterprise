import {
    Component,
    computed,
    onMounted,
    onPatched,
    onWillDestroy,
    usePlugin,
    xml,
} from "@odoo/owl";

import { Softphone } from "@voip/softphone/softphone";
import { useService } from "@web/core/utils/hooks";
import { OverlayPlugin } from "@web/core/overlay/overlay_plugin";

/**
 * Main component used to control the Softphone visibility. A main component is
 * a component that is mounted by the web client at startup.
 *
 * Notice that this mounts the Softphone itself as an overlay. The idea is that
 * the softphone should behave just like other overlays: other ones opened after
 * the softphone (including inner dropdowns in the Softphone) should be on top.
 * However, if the softphone is opened while a dialog is currently opened, we
 * want the softphone to be on top, as it is the last action asked by the user.
 * Also, we want incoming calls to bypass this and go over currently opened
 * dialogs. And then if during the call the user opens a new dialog, that one
 * should be on top again.
 */
export class SoftphoneContainer extends Component {
    static template = xml`<t t-set="overlayState" t-value="this.overlayState()"/>`;

    setup() {
        this.voip = useService("voip");
        this.overlay = usePlugin(OverlayPlugin);
        this.softphone = this.voip.softphone;
        this.prevShouldBeOnTop = this.softphone.shouldBeOnTop();
        this.overlayState = computed(() => ({
            isDisplayed: this.softphone.isDisplayed,
            shouldBeOnTop: this.softphone.shouldBeOnTop(),
        }));
        onMounted(() => this._applySoftphoneOverlayState());
        onPatched(() => this._applySoftphoneOverlayState());
        onWillDestroy(() => this._hideSoftphone());
    }

    _applySoftphoneOverlayState() {
        const { isDisplayed, shouldBeOnTop } = this.overlayState();
        if (!isDisplayed) {
            // Asking to hide: just always hide
            this._hideSoftphone();
        } else if (!this.isSoftphoneShown) {
            // Asking to show: do it directly if not already shown
            this._showSoftphone();
        } else if (shouldBeOnTop && !this.prevShouldBeOnTop) {
            // Asking to show but was already shown: the softphone may
            // want to be promoted to the top. This is done by hiding
            // the softphone and re-showing.
            this._hideSoftphone();
            this._showSoftphone();
        }
        this.prevShouldBeOnTop = shouldBeOnTop;
    }

    /**
     * Indicates if the softphone is currently being shown as an overlay.
     */
    get isSoftphoneShown() {
        return Boolean(this._doHideSoftphone);
    }

    /**
     * Shows the softphone as an overlay. If already shown, this does nothing.
     */
    _showSoftphone() {
        if (this.isSoftphoneShown) {
            return;
        }
        this._doHideSoftphone = this.overlay.add(Softphone, {});
    }

    /**
     * Hides the softphone. If not currently shown, this does nothing.
     */
    _hideSoftphone() {
        if (!this.isSoftphoneShown) {
            return;
        }
        this._doHideSoftphone();
        this._doHideSoftphone = undefined;
    }
}
