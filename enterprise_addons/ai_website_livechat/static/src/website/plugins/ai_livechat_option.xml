<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">

<t t-name="ai_website_livechat.AILivechatOption">
    <BuilderRow label.translate="Chat Style">
        <BuilderSelect action="'setChatStyle'" preview="false">
            <BuilderSelectItem actionParam="'popup'" title.translate="Popup Window">Popup Window</BuilderSelectItem>
            <BuilderSelectItem actionParam="'fullscreen'" title.translate="Fullscreen">Fullscreen</BuilderSelectItem>
        </BuilderSelect>
    </BuilderRow>
    <BuilderRow label.translate="AI Agent">
        <BuilderMany2One action="'setAIAgent'" model="'ai.agent'" domain="[['is_system_agent', '=', false]]"/>
    </BuilderRow>
    <BuilderRow label.translate="Live Chat Channel" tooltip.translate="Displayed only when a support person is available">
        <BuilderMany2One action="'setLivechatChannel'" model="'im_livechat.channel'"/>
    </BuilderRow>
    <BuilderRow label.translate="Prompt Placeholder">
        <BuilderTextInput action="'setPromptPlaceholder'" placeholder.translate="e.g. Ask AI"/>
    </BuilderRow>
    <BuilderRow label.translate="Fallback Button" tooltip.translate="Displayed when there are no support personnel online">
        <BuilderCheckbox action="'toggleHasFallbackButton'" id="'aiLivechatFallbackButton'"/>
    </BuilderRow>
    <BuilderRow label.translate="Text" level="1" t-if="this.isActiveItem('aiLivechatFallbackButton')">
        <BuilderTextInput action="'setFallbackButtonText'" placeholder.translate="e.g. Contact Us" default="''"/>
    </BuilderRow>
    <BuilderRow label.translate="URL" level="1" t-if="this.isActiveItem('aiLivechatFallbackButton')">
        <BuilderUrlPicker action="'setFallbackButtonURL'" placeholder.translate="e.g. /contactus" default="''"/>
    </BuilderRow>
    <hr/>
</t>

<t t-inherit="website.BuilderOptions" t-inherit-mode="extension">
    <xpath expr="//t[@id='snippet_specific_options']" position="after">
        <ai_livechat_option
            template="ai_website_livechat.AILivechatOption"
            selector=".s_ai_livechat"/>
    </xpath>
</t>

</templates>
