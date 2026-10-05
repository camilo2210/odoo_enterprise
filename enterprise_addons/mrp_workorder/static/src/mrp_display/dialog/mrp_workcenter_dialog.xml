<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
    <t t-name="mrp_workorder.MrpWorkcenterDialog">
        <Dialog size="this.state.noWorkcenters ? 'sm' : 'lg'" title="this.props.title" modalRef="this.modalRef">
                <div class="o_mrp_workcenter_dialog container px-0">
                    <div class="row row-cols-1 row-cols-sm-2 row-cols-md-3 row-cols-lg-4 g-2">
                        <t t-foreach="this.workcenters" t-as="workcenter" t-key="workcenter.id">
                            <div class="col">
                                <div class="o_workcenter_button form-check btn btn-outline-secondary d-flex align-items-center py-3 w-100 h-100 text-start"
                                     t-att-class="{'active' : this.active(workcenter)}"
                                     t-on-click.prevent="() => this.selectWorkcenter(workcenter)">
                                    <label class="form-check-label cursor-pointer"
                                           t-out="workcenter.display_name"
                                           t-att-for="'o_workcenter_checkbox_' + workcenter.id"/>
                                    <input class="form-check-input ms-auto"
                                           type="checkbox"
                                           t-att-id="'o_workcenter_checkbox_' + workcenter.id"
                                           t-att-checked="this.active(workcenter)"/>
                                </div>
                            </div>
                        </t>
                    </div>
                    <div t-if="this.state.noWorkcenters" class="d-flex flex-column mx-auto">
                            <button class="btn btn-primary btn-lg mb-2" t-on-click="this.createWorkcenter">
                                Create new work center
                            </button>
                            <button class="btn btn-secondary btn-lg" t-on-click="this.confirm">
                                Configure later
                            </button>
                        </div>
                    <t t-set-slot="footer" t-if="!this.state.noWorkcenters">
                        <button class="btn btn-primary" t-att-class="{'disabled': this.props.radioMode &amp;&amp; !this.state.activeWorkcenters.length}" t-on-click="this.confirm">Confirm</button>
                        <button class="btn btn-secondary" t-on-click="this._cancel">Discard</button>
                    </t>
                </div>
        </Dialog>
    </t>
</templates>
