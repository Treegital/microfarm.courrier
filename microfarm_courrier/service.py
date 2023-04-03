import email
import logging
import typing as t
from pathlib import Path
from mailbox import Maildir
from aiozmq import rpc
from minicli import cli, run
from postrider import create_message
from postrider.queue import ProcessorThread
from postrider.mailer import SMTPConfiguration, Courrier


rpc_logger = logging.getLogger('microfarm_courrier.rpc')
mailbox_logger = logging.getLogger('microfarm_courrier.mailbox')


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
                worker, emitter = self.workers[key]
                message = create_message(
                    emitter,
                    recipients,
                    subject,
                    text,
                    html
                ).as_string()

                msg = email.message_from_string(message)
                worker.mailbox.add(msg)
                return {"msg": "Email enqueued."}
            except Exception as err:
                import pdb
                pdb.set_trace()
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
        mailbox_logger.debug(f'Creating maidir worker: {name}.')
        worker = workers[name] = (thread, config['emitter'])
        mailbox_logger.debug(f'Starting maidir worker: {name}.')
        thread.start()
    try:
        service = CourrierService(workers)
        server = await rpc.serve_rpc(service, bind=settings['rpc']['bind'])
        rpc_logger.info(f"Courrier RPC Service ({settings['rpc']['bind']})")
        await server.wait_closed()
    finally:
        for worker, config in workers.values():
            worker.stop()
            worker.join()


if __name__ == '__main__':
    run()
