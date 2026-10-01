# keep these before res_partner import
from . import voip_phone_country_mixin
from . import voip_pbx_destination_mixin
from . import voip_call_flow_member_mixin
from . import voip_activity_mixin
from . import voip_extension_destination_mixin

from . import voip_provider   # keep this before res_users_settings

from . import ir_config_parameter
from . import ir_http
from . import ir_qweb
from . import mail_activity
from . import mail_call_artifact
from . import pbx_service
from . import phone_service_api
from . import phone_service_event
from . import res_country
from . import res_partner
from . import res_users
from . import res_users_settings
from . import utils
from . import voip_call
from . import voip_call_flow
from . import voip_call_cost_line
from . import voip_call_group
from . import voip_call_leg
from . import voip_conversation
from . import voip_did_number
from . import voip_did_number_request
from . import voip_extension
from . import voip_sound  # keep this before voip_ivr (_inherits)
from . import voip_ivr
from . import voip_music_on_hold
from . import voip_queue
from . import voip_queue_agent
from . import voip_requirement
from . import voip_requirement_group
from . import voip_time_condition
from . import voip_voicemail
from . import voip_voicemail_message
