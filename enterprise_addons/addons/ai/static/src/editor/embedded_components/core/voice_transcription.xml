<?xml version="1.0" encoding="utf-8"?>
<templates id="template" xml:space="preserve">
    <t t-name="ai.VoiceTranscription">
        <details class="transcript-block border mb-2" t-att-open="this.state.isOpened">
            <summary class="d-flex bg-100 px-2 py-1 fw-bold gap-1 justify-content-between" t-on-click="() => this.state.isOpened = !this.state.isOpened" t-att-class="{'py-2': !this.state.isOpened}">
                <t t-if="this.state.isOpened">
                    <t t-if="this.ui.size gt 2">
                        <div class="d-flex align-items-center">
                            <i class="oi flex-0 me-2" data-icon="arrow_drop_down" />
                            <ul class="nav gap-1 px-0 bg-transparent" role="tablist">
                                <li t-if="this.state.hasSummary || this.state.status === 'summarizing'">
                                    <button
                                        class="btn flex-grow-1 flex-sm-grow-0 w-100 w-sm-auto text-muted"
                                        t-att-class="{'btn-secondary active text-primary': this.state.currentTab === 'summary'}"
                                        t-on-click.stop="() => this.setCurrentTab('summary')"
                                        t-att-disabled="this.state.status === 'summarizing'">
                                        <t t-if="this.state.status === 'summarizing'">
                                            <div class="spinner-border spinner-border-sm me-1" role="status"/>
                                            Processing...
                                        </t>
                                        <t t-else="">
                                            <img src="/ai/static/description/icon.png" class="ai-icon-sm me-1 w-1"/>
                                            Summary
                                        </t>
                                    </button>
                                </li>
                                <li>
                                    <button class="btn flex-sm-grow-0 w-100 w-sm-auto text-muted"
                                        t-att-class="{'btn-secondary active text-primary': this.state.currentTab === 'notes'}"
                                        t-on-click.stop="() => this.setCurrentTab('notes')">
                                        <i class="oi me-1" data-icon="menu"/>
                                        Notes
                                    </button>
                                </li>
                                <li>
                                    <button
                                        class="btn flex-sm-grow-0 w-100 w-sm-auto text-muted"
                                        t-att-class="{'btn-secondary active text-primary': this.state.currentTab === 'transcript'}"
                                        t-on-click.stop="() => this.setCurrentTab('transcript')">
                                        <i class="oi me-1" data-icon="mic"/>
                                        Transcript
                                    </button>
                                </li>
                            </ul>
                        </div>
                        <AudioVisualizer t-if="this.state.status === 'recording' and this.state.frequencies.length > 0" frequencies="this.state.frequencies"/>
                        <div class="d-flex flex-wrap gap-1" t-if="this.state.currentTab !== 'summary'">
                            <Dropdown t-if="this.supportedLanguages?.length > 1">
                                <button class="btn btn-secondary o-dropdown-caret px-2">
                                    <t t-out="this.state.currentLanguage.shortCode" />
                                </button>
                                <t t-set-slot="content">
                                    <t t-foreach="this.supportedLanguages" t-as="language" t-key="language_index">
                                        <DropdownItem class="`btn btn-link ${language.code === this.state.currentLanguage.code ? 'active' : ''}`" onSelected="() => this.state.currentLanguage = language">
                                            <t t-out="language.shortCode" />
                                        </DropdownItem>
                                    </t>
                                </t>
                            </Dropdown>
                            <button
                                class="btn btn-secondary flex-sm-grow-0 w-100 w-sm-auto"
                                t-on-click.stop="this.toggleRecording"
                                t-att-disabled="this.state.status === 'summarizing' || this.state.status === 'waiting'">
                                <t t-if="this.state.status === 'recording'">
                                    <i class="oi text-danger me-1" data-icon="stop"/>
                                    Stop Recording
                                </t>
                                <t t-else="">
                                    <i class="oi oi-filled text-danger me-1" data-icon="circle"/>
                                    Start Recording
                                </t>
                            </button>
                        </div>
                        <button class="btn btn-secondary ms-lg-auto" t-on-click.stop="this.openComposer" t-att-disabled="this.state.status === 'summarizing'" t-else="">
                            <i class="oi oi-filled me-1" data-icon="mail"/>
                            Share by email
                        </button>
                    </t>
                    <t t-else="">
                        <Dropdown>
                            <button class="btn btn-secondary o-dropdown-caret px-2 px-sm-3">
                                <t t-if="this.state.currentTab === 'summary'">
                                    <img src="/ai/static/description/icon.png" class="ai-icon-sm me-1"/> Summary
                                </t>
                                <t t-elif="this.state.currentTab === 'notes'">
                                    <i class="oi me-1" data-icon="menu"/>Notes
                                </t>
                                <t t-else="">
                                    <i class="oi me-1" data-icon="mic"/>Transcript
                                </t>
                            </button>
                            <t t-set-slot="content">
                                <DropdownItem class="`btn btn-link ${this.state.currentTab === 'summary' ? 'active' : ''}`" onSelected="(ev) => this.setCurrentTab('summary')">
                                    <img src="/ai/static/description/icon.png" class="ai-icon-sm me-1"/>Summary
                                </DropdownItem>
                                <DropdownItem class="`btn btn-link ${this.state.currentTab === 'notes' ? 'active' : ''}`" onSelected="(ev) => this.setCurrentTab('notes')">
                                    <i class="oi me-1" data-icon="menu"/>Notes
                                </DropdownItem>
                                <DropdownItem class="`btn btn-link ${this.state.currentTab === 'transcript' ? 'active' : ''}`" onSelected="(ev) => this.setCurrentTab('transcript')">
                                    <i class="oi me-1" data-icon="mic"/>Transcript
                                </DropdownItem>
                            </t>
                        </Dropdown>
                        <AudioVisualizer t-if="this.state.status === 'recording' and this.state.frequencies.length > 0" frequencies="this.state.frequencies"/>
                        <div class="d-flex">
                            <Dropdown t-if="this.state.hasSummary || this.supportedLanguages?.length > 1">
                                <button class="btn">
                                    <i class="oi" data-icon="more_vert"/>
                                </button>
                                <t t-set-slot="content">
                                    <DropdownItem class="'btn btn-link p-0'">
                                        <Dropdown t-if="this.supportedLanguages?.length > 1">
                                            <button class="btn o-dropdown-caret">
                                                Language
                                                <span class="ms-2 fw-normal text-muted">
                                                    <t t-out="this.state.currentLanguage.shortCode" />
                                                </span>
                                            </button>
                                            <t t-set-slot="content">
                                                <t t-foreach="this.supportedLanguages" t-as="language" t-key="language_index">
                                                    <DropdownItem
                                                        class="`btn btn-link ${language.code === this.state.currentLanguage.code ? 'active' : ''}`"
                                                        onSelected="() => this.state.currentLanguage = language">
                                                        <t t-out="language.shortCode" />
                                                    </DropdownItem>
                                                </t>
                                            </t>
                                        </Dropdown>
                                    </DropdownItem>
                                    <DropdownItem class="'btn btn-link'" t-if="this.state.hasSummary" onSelected="(ev) => this.openComposer()">
                                        <i class="oi oi-filled me-1" data-icon="mail"/>
                                        Share by email
                                    </DropdownItem>
                                </t>
                            </Dropdown>
                            <button
                                class="btn btn-secondary px-2 px-sm-3"
                                t-on-click.stop="this.toggleRecording"
                                t-att-disabled="this.state.status === 'summarizing' || this.state.status === 'waiting'">
                                <t t-if="this.state.status === 'recording'">
                                    <i class="oi text-danger me-1" data-icon="stop" />
                                    Stop
                                </t>
                                <t t-else="">
                                    <i class="oi oi-filled text-danger me-1" data-icon="circle" />
                                    Start
                                </t>
                            </button>
                        </div>
                    </t>
                </t>
                <t t-else="">
                    <div class="d-flex align-items-center">
                        <i class="oi flex-0 me-1" data-icon="arrow_right"/>
                        Voice Recording <span t-out="this.state.firstRecordingDate" class="ms-2 fw-normal text-muted"/>
                    </div>
                    <AudioVisualizer t-if="this.state.status === 'recording' and this.state.frequencies.length > 0" frequencies="this.state.frequencies" maxHeight="24"/>
                </t>
            </summary>
            <div class="detail-content overflow-auto"  t-att-class="{'d-none': this.state.currentTab !== 'summary'}">
                <header t-if="this.sortedPromptButtons.length > 0" class="d-flex gap-2 flex-wrap mb-2">
                    <t t-if="this.ui.size gt 2">
                        <t t-foreach="this.sortedPromptButtons" t-as="promptButton" t-key="promptButton_index">
                            <button class="btn btn-secondary" t-on-click="() => this.updateSummary(promptButton)">
                                <t t-out="promptButton.name" />
                            </button>
                        </t>
                    </t>
                    <t t-else="">
                        <Dropdown>
                            <button class="btn btn-secondary o-dropdown-caret">Actions</button>
                            <t t-set-slot="content">
                                <t t-foreach="this.sortedPromptButtons" t-as="promptButton" t-key="promptButton_index">
                                    <DropdownItem class="'btn btn-link'" onSelected="() => this.updateSummary(promptButton)">
                                        <t t-out="promptButton.name"/>
                                    </DropdownItem>
                                </t>
                            </t>
                        </Dropdown>
                    </t>
                </header>
                <div id="summary-content"  t-ref="this.descendantRefs.summaryContent" t-att-class="{ 'o-ai-summary-processing': this.state.status === 'summarizing' }"/>
            </div>
            <div id="notes-content" class="detail-content overflow-auto" t-att-class="{'d-none': this.state.currentTab !== 'notes'}" t-ref="this.descendantRefs.notesContent"/>
            <div id="transcript-content" class="detail-content overflow-auto" t-att-class="{'d-none': this.state.currentTab !== 'transcript'}" t-ref="this.descendantRefs.transcriptContent"/>
        </details>
    </t>
</templates>
