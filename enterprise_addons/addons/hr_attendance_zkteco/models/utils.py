from odoo.tools.urls import urljoin


def _notification(message, title=None, notification_type="success", reload="soft_reload"):
    params = {"message": message, "type": notification_type, "sticky": False}
    if title:
        params["title"] = title
    if reload:
        params["next"] = {"type": "ir.actions.client", "tag": reload}

    return {"type": "ir.actions.client", "tag": "display_notification", "params": params}


def _get_records_from_server(session, path, params=None):
    records = []
    url = urljoin(session.base_url, path)
    params = {"page_size": 100, **(params or {})}

    while url:
        response = session.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        records.extend(data.get("data", []))
        url = data.get("next")
        params = None

    return records
