import json
import logging
from typing import Callable, List

from azure.servicebus import ServiceBusClient, ServiceBusMessage
from common.utils import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


MAX_BATCH_SIZE = 3
MAX_WAIT_TIME = 5

class ServiceBusConsumer:
    def __init__(
        self,
        conn_str: str,
        topic_name: str,
        subscription_name: str,
    ):
        self.topic_name = topic_name
        self.subscription_name = subscription_name
        self.client = ServiceBusClient.from_connection_string(conn_str)

    def consume_batch(self, handler: Callable[[List[dict]], None]):
        """
        handler(payload_dict) -> None
        """

        with self.client:
            receiver = self.client.get_subscription_receiver(
                topic_name=self.topic_name,
                subscription_name=self.subscription_name,
                max_wait_time=MAX_WAIT_TIME,
                prefetch_count=MAX_BATCH_SIZE,
            )

            with receiver:
                messages = receiver.receive_messages(
                    max_message_count=MAX_BATCH_SIZE,
                    max_wait_time=30
                )

                if not messages:
                    logger.info("No messages received — exiting job")
                    return
                
                payloads = []
                completed = []

                for message in messages:
                    logger.info(f"Post received: {message}")
                    payload = json.loads(str(message))
                    payloads.append(payload)
                    completed.append(message)

                handler(payloads)

                for message in messages:
                    receiver.complete_message(message)

                logger.info(f"Complete {len(completed)} messages, job completed")