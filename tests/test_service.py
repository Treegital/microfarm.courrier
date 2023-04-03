import pytest
import time
from freezegun import freeze_time


@pytest.mark.asyncio
async def test_send_email_wrong_key(courrier_service, courrier_client):
    response = await courrier_client.send_email(
        'key',
        ['test@gmail.com'],
        subject='test with wrong key',
        text='I do not know this key.'
    )
    assert response == {'err': 'unknown mailer'}


@pytest.mark.asyncio
async def test_send_email(
        courrier_service, courrier_client, courrier_workers, maildir, smtpd):
    assert len(maildir) == 0
    response = await courrier_client.send_email(
        'test',
        ['test@gmail.com'],
        subject='test with wrong key',
        text='I do not know this key.'
    )
    assert response == {'msg': 'Email enqueued.'}
    assert len(maildir) == 1

    worker, emitter = courrier_workers['test']
    worker.run(forever=False)

    assert len(smtpd.messages) == 1
