<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
    <t t-name="hr_expense_stripe.stripeAttachment" >
        <div class="o_stripe_attachment">
            <div class="d-flex align-items-center">
                <t t-if="this.isFilePresent">
                    <span class="o_stripe_attachment_title me-3" t-esc="this.props.title || this.props.name"/>
                    <button type="button"
                            class="btn btn-primary btn-sm me-2"
                            t-on-click="this.downloadFile"
                            t-if="this.isDownloadable">
                        <i class="oi" data-icon="download" aria-hidden="true"/>
                    </button>
                    <button type="button"
                            class="btn btn-secondary btn-sm text-danger"
                            t-on-click="this.deleteFile"
                            title="Delete"
                            t-if="!this.isReadOnly">
                        <i class="oi" data-icon="delete" aria-hidden="true"/>
                    </button>
                </t>
                <t t-else="">
                    <label class="btn btn-secondary btn-sm mb-0"
                           t-att-for="'stripe-file-' + this.props.id"
                           t-att-class="{'disabled': this.isReadOnly}">
                        <i class="oi me-1" data-icon="upload" aria-hidden="true"/> Upload <t t-esc="this.props.title || this.props.name"/>
                    </label>
                    <input t-att-id="'stripe-file-' + this.props.id"
                           type="file"
                           class="d-none"
                           t-on-change="this.uploadFile"
                           accept="application/pdf,image/jpeg,image/png"/>
                </t>
            </div>
        </div>
    </t>
</templates>
