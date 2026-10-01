<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
    <t t-name="l10n_ch_hr_payroll.StatusResultWidgetTemplate">
        <div class="o_swissdec_json_widget p-3">
            <t t-if="this.response_state">
                <!-- Warnings -->
                <t t-if="this.response_state.Warning">
                    <SwissdecNotification type="'warning'" notifications="this.response_state.Warning.Notification"/>
                </t>
                <!-- Infos -->
                <t t-if="this.response_state.Info">
                    <SwissdecNotification type="'info'" notifications="this.response_state.Info.Notification"/>
                </t>
            </t>
            <t t-if="this.error">
                <t t-if="this.error.EndUserInformation">
                    <div class="alert alert-danger" role="alert">
                        <h4 class="alert-heading"><i class="oi oi-filled me-2" data-icon="cancel"></i>Error</h4>
                        <hr/>
                        <p class="mb-0 text-muted" t-out="this.error.EndUserInformation"/>
                    </div>
                </t>
                <t t-if="this.error.DetailInformation">
                    <div class="alert alert-danger mt-2" role="alert">
                        <h4 class="alert-heading"><i class="oi oi-filled me-2" data-icon="cancel"></i>Details</h4>
                        <hr/>
                        <p class="mb-0 text-muted" t-out="this.error.DetailInformation"/>
                    </div>
                </t>
                <t t-if="this.error.FaultInformation">
                    <t t-set="fault_context" t-value="this.error.FaultInformation.FaultContext"/>
                    <t t-set="Fault_state" t-value="this.error.FaultInformation.FaultState"/>

                    <div class="card mt-2 border-danger">
                        <div class="card-header bg-danger text-white">
                            <i class="oi me-2" data-icon="bug_report"></i>Fault Information
                        </div>
                        <div class="card-body">
                            <ul class="list-unstyled mb-2">
                                <li><b>InstitutionName:</b> <t t-out="fault_context.InstitutionName"/></li>
                                <li><b>TransmissionDate:</b> <t t-out="fault_context.TransmissionDate"/></li>
                                <li><b>ResponseID:</b> <t t-out="fault_context.ResponseID"/></li>
                                <li><b>RequestID:</b> <t t-out="fault_context.RequestID"/></li>
                            </ul>

                            <!-- Fault Notifications -->
                            <t t-if="Fault_state.Error">
                                <SwissdecNotification type="'error'" notifications="Fault_state.Error.Notification"/>
                            </t>
                            <t t-if="Fault_state.Warning">
                                <SwissdecNotification type="'warning'" notifications="Fault_state.Warning.Notification"/>
                            </t>
                            <t t-if="Fault_state.Info">
                                <SwissdecNotification type="'info'" notifications="Fault_state.Info.Notification"/>
                            </t>
                        </div>
                </div>
            </t>
            </t>
        </div>
    </t>
</templates>