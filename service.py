import pika
import dynaconf
import sys
import logging
from mailbox import Maildir
from postrider.mailer import SMTPConfiguration, Courrier
from postrider.queue import ProcessorThread
from postrider import create_message


def configure_logging(log_level=logging.WARNING):
    stream_handler = logging.StreamHandler(stream=sys.stdout)
    stream_handler.setLevel(log_level)
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s %(levelname)s %(module)s %(funcName)s %(message)s',
        handlers=[stream_handler]
    )


def create_connection():
    credentials = pika.PlainCredentials("guest", "guest")
    parameters = pika.ConnectionParameters(
        "localhost", credentials=credentials
    )
    connection = pika.BlockingConnection(parameters)
    return connection


def emailer_service(workers):
    connection = create_connection()
    try:
        channel = connection.channel()
        generator = channel.consume("mailing")
        for method_frame, properties, body in generator:
            worker, config = workers[method_frame.routing_key]
            message = create_message(
                config.emitter, ['test@example.com'], 'subject', body.decode())
            worker.mailbox.add(message)
            channel.basic_ack(method_frame.delivery_tag)
    finally:
        if connection.is_open:
            connection.close()


if __name__ == '__main__':
    settings = dynaconf.Dynaconf(settings_files=["emailer.toml"])
    courrier = Courrier(SMTPConfiguration(**settings.smtp))
    configure_logging()

    workers = {}
    for emailer, config in settings['mailbox'].items():
        thread = ProcessorThread(
            courrier,
            Maildir(config.mailbox),
            5.0  # salvo every 5 sec
        )
        workers[f'mailing.{config.key}'] = (thread, config)

    for worker, config in workers.values():
        worker.start()
    try:
        emailer_service(workers)
    finally:
        for worker, config in workers.values():
            worker.stop()
            worker.join()
