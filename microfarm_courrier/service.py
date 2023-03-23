import asyncio
import time
import email
import sys
import logging
import typing as t
from pathlib import Path
from minicli import cli, run
from mailbox import Maildir
from postrider import create_message
from postrider.queue import ProcessorThread
from postrider.mailer import SMTPConfiguration, Courrier
from aiozmq import rpc


def configure_logging(log_level=logging.WARNING):
    stream_handler = logging.StreamHandler(stream=sys.stdout)
    stream_handler.setLevel(log_level)
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s %(levelname)s %(module)s %(funcName)s %(message)s',
        handlers=[stream_handler]
    )


class CourrierService(rpc.AttrHandler):

    def __init__(self, workers):
        self.workers = workers

    @rpc.method
    def send_email(self,
                   key: str,
                   recipients: t.Iterable[str],
                   subject: str,
                   text: str,
                   html: t.Optional[str] = None):

        if key in self.workers:
            try:
                worker, config = self.workers[key]
                message = create_message(
                    config.emitter,
                    recipients,
                    subject,
                    text,
                    html
                ).as_string()

                msg = email.message_from_string(message)
                worker.mailbox.add(msg)
                return True
            except:
                return {"err": "Email corrupted"}
        else:
            return {"err": "unknown mailer"}


@cli
async def serve(config: Path):
    import tomli
    import logging.config

    assert config.is_file()
    with config.open("rb") as f:
        settings = tomli.load(f)

    if logconf := settings.get('logging'):
        logging.config.dictConfigClass(logconf).configure()

    courrier = Courrier(SMTPConfiguration(**settings['smtp']))
    workers = {}
    for name, config in settings['mailbox'].items():
        thread = ProcessorThread(
            courrier,
            Maildir(config['path']),
            5.0  # salvo every 5 sec
        )
        workers[name] = (thread, config)

    for worker, config in workers.values():
        worker.start()
    try:
        service = CourrierService(workers)
        server = await rpc.serve_rpc(service, bind=settings['rpc']['bind'])
        await server.wait_closed()
    finally:
        for worker, config in workers.values():
            worker.stop()
            worker.join()


if __name__ == '__main__':
    run()
