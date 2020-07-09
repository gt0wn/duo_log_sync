"""
Definition of the Consumer class
"""

import sys
import json
import asyncio
import logging
from duologsync.util import get_polling_duration, update_log_checkpoint

class Consumer():
    """
    Read logs from a log API call function provided by a log-specific producer
    object and write those logs somewhere using the writer object passed.
    Additionally, once logs have been written successfully, take the latest
    log_offset - also shared with the Producer pair - and save it to a
    checkpointing file in order to recover progress if a crash occurs.
    """

    def __init__(self, producer, writer):
        self.log_offset = None
        self.producer = producer
        self.writer = writer
        self.log_type = None

    async def consume(self):
        """
        Consumer that will consume data from using a log API call function
        from producer. This data is then sent over a configured transport
        protocol to respective SIEMs or server.
        """
        while True:
            logging.info("Consuming %s logs...", self.log_type)
            asyncio.sleep(get_polling_duration())
            api_result = await self.producer.call_log_api()
            logs = self.producer.get_logs(api_result)

            if logs is None:
                logging.info("%s logs empty. Nothing to write...", self.log_type)
                continue

            logging.info("Consumed %s %s logs...", len(logs), self.log_type)

            save_log = None

            try:
                for log in logs:
                    self.writer.write(json.dumps(log).encode() + b'\n')
                    await self.writer.drain()
                    save_log = log
                self.log_offset = self.producer.get_api_result_offset(api_result)
                logging.info("Wrote data over tcp socket...")
            except Exception as error:
                logging.error("Failed to write data to transport: %s", error)
                sys.exit(1)

            self.log_offset = self.producer.get_log_offset(save_log)

            # Save log_offset to log specific checkpoint file
            update_log_checkpoint(self.log_type, self.log_offset)
