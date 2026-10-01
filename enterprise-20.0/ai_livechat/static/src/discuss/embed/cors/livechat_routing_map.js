import { livechatRoutingMap } from "@im_livechat/embed/cors/livechat_routing_map";

livechatRoutingMap
    .add("/ai/start_session_advance", "/ai/cors/start_session_advance")
    .add("/ai/resume_pending_interaction", "/ai/cors/resume_pending_interaction")
    .add("/ai_livechat/forward_operator", "/ai_livechat/cors/forward_operator");
