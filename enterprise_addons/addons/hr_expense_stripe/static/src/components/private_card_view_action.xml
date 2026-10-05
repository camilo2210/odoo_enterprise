<?xml version="1.0" encoding="utf-8"?>
<templates xml:space="preserve">
    <t t-name="hr_expense_stripe.privateCardViewDialog">
        <script type="text/javascript" src="https://js.stripe.com/v3/"></script>
        <Dialog t-if="this.state.ephemeralKey" size="'md'" title.translate="My Card" footer="false">
            <article class="stripe_record_card stripe_record_card_private d-flex justify-content-center">
                <div class="stripe_record_card_element">
                    <div class="d-flex flex-row justify-content-end stripe_card_text_sm stripe_card_text_type" t-out="this.state.card.type"/>
                    <div class="d-flex flex-column h-75 mt-auto justify-content-end">
                        <span class="card_name w-100 stripe_card_text mb-2" t-out="this.state.card.name"/>
                        <div class="d-flex w-100 h-50 justify-content-between">
                            <div class="d-flex flex-column justify-content-between w-75">
                                <div class="d-flex w-100 justify-content-between align-items-top">
                                    <span class="w-100" t-ref="this.numberPlaceholderRef"/>
                                    <div class="position-relative">
                                        <i class="oi stripe_card_text_sm" data-icon="content_copy"/>
                                        <span class="position-absolute start-0 top-0 w-100 card_icon" t-ref="this.numberCopyPlaceholderRef">
                                        </span>
                                    </div>
                                </div>
                                <div class="d-flex w-100 justify-content-between align-items-center">
                                    <span class="card_expiry d-flex w-50 stripe_card_text_sm align-items-center" t-out="this.state.card.exp"/>
                                    <div class="d-flex justify-content-between w-50 align-items-center">
                                        <span class="w-100" style="margin-left: 28%" t-ref="this.cvcPlaceholderRef"/>
                                        <div class="position-relative">
                                            <i class="oi stripe_card_text_sm" data-icon="content_copy"/>
                                            <span class="position-absolute start-0 top-0 w-100 card_icon" t-ref="this.cvcCopyPlaceholderRef">
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <h1 class="align-self-end">
                                <i class="mastercard-icon"/>
                            </h1>
                        </div>
                    </div>
                </div>
            </article>
            <div class="d-flex justify-content-center mt-3 p-2">
                <label class="stripe_card_text_sm mx-1 w-50 text-end align-content-center" for="pinPlaceholder">PIN Number:</label>
                <span t-ref="this.pinPlaceholderRef" id="pinPlaceholder" class="w-50 mx-1 align-content-center"/>
            </div>
        </Dialog>
        <Dialog t-else="" size="'md'" title.translate="Two-Factor Authentification">
            <div class="d-flex flex-column mx-auto gap-3">
                <div><t t-out="this.state.message"/></div>
                <InputVerificationCode nbInputs="6" onValidatedInput.bind="this.requestEphemeralKey"/>
            </div>
            <t t-set-slot="footer">
                <button class="btn btn-primary" t-on-click="this.close">Close</button>
                <button class="btn btn-secondary" t-on-click="this.send2FARequest">Resend</button>
            </t>
        </Dialog>
    </t>
</templates>
