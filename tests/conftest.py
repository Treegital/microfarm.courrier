import asyncio
import pytest
import pytest_asyncio
import pathlib
from aiozmq import rpc
from mailbox import Maildir
from smtpdfix import SMTPDFix
from postrider.queue import ProcessorThread
from postrider.mailer import SMTPConfiguration, Courrier
from microfarm_courrier.service import CourrierService


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def smtpd():
    with SMTPDFix("127.0.0.1", 9999) as smtp:
        yield smtp


@pytest.fixture(scope="module")
def courrier():
    return Courrier(SMTPConfiguration(
        host="127.0.0.1",
        port=9999
    ))


@pytest.fixture(scope="session")
def maildir(tmpdir_factory):
    path = tmpdir_factory.mktemp("maildir") / "mailbox"
    return Maildir(pathlib.Path(path), create=True)


@pytest.fixture(scope="module")
def courrier_workers(courrier, maildir):
    thread = ProcessorThread(
        courrier,
        maildir,
        1  # salvo every sec
    )
    return {
        'test': (thread, 'test@test.com'),
        'toto': (thread, 'toto@test.com'),
    }


@pytest_asyncio.fixture(scope="module")
async def courrier_service(courrier_workers):
    service = CourrierService(courrier_workers)
    server = await rpc.serve_rpc(service, bind="inproc://test")
    yield server
    server.close()
    await server.wait_closed()


@pytest_asyncio.fixture(scope="module")
async def courrier_client():
    client = await rpc.connect_rpc(connect="inproc://test", timeout=0.5)
    try:
        yield client.call
    finally:
        client.close()
