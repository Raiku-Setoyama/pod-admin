"""Cloud Monitoring の Webhook 通知（schema version 1.2）.

必要な項目だけを受け取り、それ以外は無視する（Monitoring 側の項目追加で壊れないように）。
https://cloud.google.com/monitoring/support/notification-options#webhooks
"""

from pydantic import BaseModel, ConfigDict


class MonitoringDocumentation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    content: str = ""


class MonitoringIncident(BaseModel):
    model_config = ConfigDict(extra="ignore")

    incident_id: str = ""
    policy_name: str = ""
    condition_name: str = ""
    # "open"（発生）/ "closed"（回復）
    state: str = ""
    summary: str = ""
    url: str = ""
    # UNIX 秒
    started_at: int | None = None
    ended_at: int | None = None
    documentation: MonitoringDocumentation | None = None


class MonitoringWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    incident: MonitoringIncident
    version: str = ""
