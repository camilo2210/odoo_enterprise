import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, proxy, signal, useListener, usePlugin, useProps } from "@odoo/owl";
import { standardActionServiceProps } from "@web/webclient/actions/action_plugin";
import { user } from "@web/core/user";
import { DebugModePlugin } from "@web/core/debug_mode_plugin";

export class HrReferralWelcome extends Component {
    static template = "hr_referral.Welcome";
    props = useProps(standardActionServiceProps);
    static path = "referrals";
    static displayName = _t("Dashboard");

    debugMode = usePlugin(DebugModePlugin);

    reachedEnd = signal(false);
    carouselRef = signal.ref();
    dashboardData = proxy({});

    setup() {
        super.setup();

        this.actionService = useService("action");
        this.orm = useService("orm");

        // Currently owl3 doesn't auto bind in useListener, but when it does remove .bind below
        useListener(this.carouselRef, "slide.bs.carousel", this.onNextSlide.bind(this));
        onWillStart(async () => {
            Object.assign(
                this.dashboardData,
                await this.orm.call("hr.applicant", "retrieve_referral_welcome_screen", [8], {
                    context: this.props.action.context,
                })
            );
            this.dashboardData.company_id = user.activeCompany.id;
        });
    }

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------
    onNextSlide(e) {
        this.reachedEnd.set(e.to == this.onboardingLength - 1);
    }

    get onboardingLength() {
        return this.dashboardData.onboarding && this.dashboardData.onboarding.length;
    }

    get applicantId() {
        return this.dashboardData.new_friend_id;
    }

    /**
     * @private
     * @param {MouseEvent} e
     */
    async _onMessageDismissClicked(event, message_id) {
        await this.orm.call('hr.referral.alert', 'action_dismiss', [message_id]);
        this.dashboardData.message = this.dashboardData.message.filter(message => message.id !== message_id);
    }

    /**
     * Save that user has seen the onboarding screen then restart the view
     *
     * @private
     * @param {MouseEvent} e
     */
    async _completeOnboarding(completed) {
        await this.orm.call('res.users', 'action_complete_onboarding', [completed]);
        this.actionService.doAction({
            type: 'ir.actions.client',
            tag: 'hr_referral_welcome',
            name: _t('Dashboard'),
            target: 'main'
        }, {noEmptyTransition: true});
    }

    /**
     * User upgrade his level then restart the view
     *
     * @private
     * @param {MouseEvent} e
     */
    async _upgradeLevel(e) {
        await this.orm.call('hr.applicant', 'upgrade_level', []);
        this.actionService.doAction({
            type: 'ir.actions.client',
            tag: 'hr_referral_welcome',
            name: _t('Dashboard'),
            target: 'main'
        }, {noEmptyTransition: true});
    }

    /**
     * Save the new user's friend then restart the view
     *
     * @private
     * @param {MouseEvent} e
     */
    async _chooseFriend(friendId) {
        await this.orm.call('hr.applicant', 'choose_a_friend', [[this.applicantId], friendId]);
        this.actionService.doAction({
            type: 'ir.actions.client',
            tag: 'hr_referral_welcome',
            name: _t('Dashboard'),
            target: 'main'
        }, {noEmptyTransition: true});
    }

}

registry.category('actions').add('hr_referral_welcome', HrReferralWelcome);
