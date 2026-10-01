# Part of Odoo. See LICENSE file for full copyright and licensing details.
from zoneinfo import ZoneInfo

from odoo import models


class MailThread(models.AbstractModel):
    _name = 'mail.thread'
    _inherit = ['mail.thread']

    def _ai_serialize_activities_data(self):
        """Serialize planned activities data for AI context"""
        if not hasattr(self, 'activity_ids'):
            return ""
        activities_data = []
        for activity in self.activity_ids:
            activity_info = f"Activity: {activity.activity_type_id.name}"
            if activity.summary:
                activity_info += f" - {activity.summary}"
            activity_info += f" (Due: {activity.date_deadline}, Assigned to: {activity.user_id.name}, Status: {activity.state})"
            if activity.note:
                # Strip HTML tags from note and limit length
                note_text = activity.note.striptags().strip() if activity.note else ''
                if note_text:
                    activity_info += f" - Note: {note_text}"
            activities_data.append(activity_info)
        return " | ".join(activities_data) if activities_data else ""

    def _ai_serialize_messages_data(self):
        # imp: replace usages of this by ai_read?
        chatter_messages = []
        user_tz = ZoneInfo(self.env.user.tz or 'UTC')
        for message in self.message_ids:
            chatter_messages.append(
                f"({message.subtype_id.name} - {message.date.astimezone(user_tz).strftime('%Y-%m-%d %H:%M')}) {message.author_id.name}: {message.body.striptags().strip() if message.body else ''}, ",
            )
        # the messages are stored from newest to oldest - reverse them so they are formatted like the conversation history
        chatter_messages = " ".join(list(reversed(chatter_messages)))
        activities_data = self._ai_serialize_activities_data()
        if activities_data:
            chatter_messages += f" Additionally, this chatter has the following planned activities: {activities_data}"

        return chatter_messages
