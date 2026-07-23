from __future__ import annotations

from dataclasses import dataclass

import pytest

from paperagent.literature.verification import (
    JsonVerificationAttemptCache,
    SQLiteVerificationAttemptCache,
    VerificationAttempt,
    VerificationService,
)
from paperagent.schemas.literature import PaperRecord


@dataclass
class FakeVerifier:
    calls: int = 0

    async def verify(self, paper: PaperRecord) -> VerificationAttempt:
        self.calls += 1
        return VerificationAttempt(status="verified", method="fake_exact")


def doi_paper() -> PaperRecord:
    return PaperRecord(
        paper_id="paper-1",
        canonical_title="Reliable Retrieval",
        doi="10.1000/reliable",
    )


@pytest.mark.asyncio
async def test_verification_attempt_is_persisted_across_services(tmp_path) -> None:
    path = tmp_path / "retrieval.sqlite3"
    first_verifier = FakeVerifier()
    first = VerificationService(
        [first_verifier],
        cache=SQLiteVerificationAttemptCache(path),
    )

    verified = await first.verify_one(doi_paper())
    first.close()

    second_verifier = FakeVerifier()
    second = VerificationService(
        [second_verifier],
        cache=SQLiteVerificationAttemptCache(path),
    )
    replayed = await second.verify_one(doi_paper())
    second.close()

    assert verified.verification_status == "verified"
    assert replayed.verification_status == "verified"
    assert first_verifier.calls == 1
    assert second_verifier.calls == 0


@pytest.mark.asyncio
async def test_offline_verification_uses_cache_and_never_calls_network(tmp_path) -> None:
    path = tmp_path / "retrieval.sqlite3"
    writer_verifier = FakeVerifier()
    writer = VerificationService(
        [writer_verifier],
        cache=SQLiteVerificationAttemptCache(path),
    )
    await writer.verify_one(doi_paper())
    writer.close()

    offline_verifier = FakeVerifier()
    offline = VerificationService(
        [offline_verifier],
        mode="offline",
        cache=SQLiteVerificationAttemptCache(path),
    )
    paper = await offline.verify_one(doi_paper())
    offline.close()

    assert paper.verification_status == "verified"
    assert offline_verifier.calls == 0


@pytest.mark.asyncio
async def test_verification_fixture_records_and_replays_without_network(tmp_path) -> None:
    recorder_verifier = FakeVerifier()
    recorder = VerificationService(
        [recorder_verifier],
        cache=JsonVerificationAttemptCache(tmp_path, writable=True),
    )
    await recorder.verify_one(doi_paper())
    recorder.close()

    replay_verifier = FakeVerifier()
    replay = VerificationService(
        [replay_verifier],
        mode="offline",
        cache=JsonVerificationAttemptCache(tmp_path),
    )
    paper = await replay.verify_one(doi_paper())
    replay.close()

    assert paper.verification_status == "verified"
    assert replay_verifier.calls == 0
    assert (tmp_path / "verification-manifest.json").is_file()
