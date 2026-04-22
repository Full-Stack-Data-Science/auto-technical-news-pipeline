import json
import logging
from azure.servicebus import ServiceBusClient, ServiceBusMessage

from common.utils import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

class ServiceBusPublisher:
    def __init__(self, conn_str: str, topic_name: str):
        self.topic_name = topic_name
        enabled = bool(conn_str)

        if enabled:
            self.client = ServiceBusClient.from_connection_string(conn_str)
        else:
            self.client = None
            logger.warning("ServiceBusPublisher disabled: empty connection string")


    def publish(self, event_type: str, payload: dict):
        message = ServiceBusMessage(
            body=json.dumps(payload),
            subject=event_type,
            application_properties={
                "event_type": event_type,
                "source": "twitter_scraper",
            }
        )

        with self.client:
            sender = self.client.get_topic_sender(self.topic_name)
            with sender:
                sender.send_messages(message)
