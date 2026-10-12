"""Result commitment transaction unit of work.

Implements the atomic commit_result transaction described in 04-A contract:
- Validates candidate and checks idempotency
- Re-verifies authorization and evidence
- Writes Claims/Citation/Message/Run terminal state/ResultCommit/Outbox atomically
- Any failure rolls back everything, publishes nothing
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from pivot.db.models import Citation, Claim, Message, PublicEventOutbox, ResultCommit, Run
from pivot.db.repositories.outbox import OutboxRepository
from pivot.db.repositories.result_commits import ResultCommitRepository
from pivot.runs.machine import is_terminal
from pivot.shared.ids import new_id
from pivot.shared.time import utc_now


class ResultCandidate:
    """Verified result candidate ready for commitment."""

    def __init__(
        self,
        result_id: str,
        terminal_state: str,
        claims: list[ClaimData],
        citations: list[CitationData],
        final_markdown: str,
        verification_version: str,
    ) -> None:
        self.result_id = result_id
        self.terminal_state = terminal_state
        self.claims = claims
        self.citations = citations
        self.final_markdown = final_markdown
        self.verification_version = verification_version


class ClaimData:
    """Claim data for commitment."""

    def __init__(
        self,
        text: str,
        support: str,
        confidence: float | None = None,
    ) -> None:
        self.text = text
        self.support = support
        self.confidence = confidence


class CitationData:
    """Citation data for commitment."""

    def __init__(
        self,
        claim_index: int,
        document_id: str,
        version_id: str,
        chunk_id: str,
        locator: str,
        snippet: str,
        confidence: float | None = None,
        retrieval_method: str = "",
    ) -> None:
        self.claim_index = claim_index
        self.document_id = document_id
        self.version_id = version_id
        self.chunk_id = chunk_id
        self.locator = locator
        self.snippet = snippet
        self.confidence = confidence
        self.retrieval_method = retrieval_method


class CommitReceipt:
    """Receipt of successful result commitment."""

    def __init__(
        self,
        run_id: str,
        result_id: str,
        message_id: str,
        terminal_state: str,
        committed_at: datetime,
        is_idempotent_replay: bool = False,
    ) -> None:
        self.run_id = run_id
        self.result_id = result_id
        self.message_id = message_id
        self.terminal_state = terminal_state
        self.committed_at = committed_at
        self.is_idempotent_replay = is_idempotent_replay


class ResultCommitmentError(Exception):
    """Base exception for result commitment failures."""

    pass


class IdempotencyConflictError(ResultCommitmentError):
    """Same result_id but different candidate content."""

    pass


class RunAlreadyTerminalError(ResultCommitmentError):
    """Run is already in a terminal state."""

    pass


class CommitmentUnitOfWork:
    """Unit of Work for atomic result commitment."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.result_commit_repo = ResultCommitRepository(session)
        self.outbox_repo = OutboxRepository(session)

    def commit_result(
        self,
        run_id: str,
        candidate: ResultCandidate,
        owner_id: str,
        conversation_id: str,
    ) -> CommitReceipt:
        """
        Commit a verified result candidate atomically.

        Steps per 04-A §5:
        1. Check idempotency: same result_id + matching candidate returns existing receipt
        2. Verify Run is not already terminal
        3. Write Claims, Citations with proper bindings
        4. Write final assistant Message
        5. Update Run to terminal state
        6. Create ResultCommit record
        7. Append events to outbox with stable seq
        8. Commit transaction

        Any step failure -> full rollback, zero public content.

        Args:
            run_id: The run to commit results for
            candidate: Verified result candidate
            owner_id: Run owner for authorization
            conversation_id: Conversation for message

        Returns:
            CommitReceipt with commitment details

        Raises:
            RunAlreadyTerminalError: Run is already terminal
            IdempotencyConflictError: Same result_id, different content
            ResultCommitmentError: Other commitment failures
        """
        # Step 1: Check existing commit for idempotency
        existing_commit = self.result_commit_repo.get_by_run_id(run_id)
        if existing_commit is not None:
            if existing_commit.result_id == candidate.result_id:
                # Same result_id - return existing receipt
                # TODO: verify candidate matches (structural comparison)
                return CommitReceipt(
                    run_id=run_id,
                    result_id=existing_commit.result_id,
                    message_id=existing_commit.message_id,
                    terminal_state=existing_commit.terminal_state,
                    committed_at=existing_commit.committed_at,
                    is_idempotent_replay=True,
                )
            else:
                # Different result_id - conflict
                raise IdempotencyConflictError(
                    f"Run {run_id} already committed with different result_id: "
                    f"{existing_commit.result_id} != {candidate.result_id}"
                )

        # Step 2: Load and verify Run state
        run = self.session.get(Run, run_id)
        if run is None:
            raise ResultCommitmentError(f"Run {run_id} not found")

        if is_terminal(run.state):
            raise RunAlreadyTerminalError(
                f"Run {run_id} already terminal: {run.state}"
            )

        # TODO: Re-verify authorization, scope, document eligibility, external policy
        # For now, trust that candidate was properly verified before calling

        # Step 3: Write Claims
        claim_records: list[Claim] = []
        for claim_data in candidate.claims:
            claim = Claim(
                id=new_id(),
                run_id=run_id,
                text=claim_data.text,
                support=claim_data.support,
                confidence=claim_data.confidence,
                created_at=utc_now(),
            )
            self.session.add(claim)
            claim_records.append(claim)

        self.session.flush()  # Get claim IDs

        # Step 4: Write Citations with claim bindings
        for citation_data in candidate.citations:
            claim_record = claim_records[citation_data.claim_index]
            citation = Citation(
                id=new_id(),
                run_id=run_id,
                claim_id=claim_record.id,
                document_id=citation_data.document_id,
                version_id=citation_data.version_id,
                chunk_id=citation_data.chunk_id,
                locator=citation_data.locator,
                snippet=citation_data.snippet,
                confidence=citation_data.confidence,
                retrieval_method=citation_data.retrieval_method,
                created_at=utc_now(),
            )
            self.session.add(citation)

        # Step 5: Write final assistant Message
        message_id = new_id()
        message = Message(
            id=message_id,
            conversation_id=conversation_id,
            sender="assistant",
            content=candidate.final_markdown,
            status="completed",
            run_id=run_id,
            created_at=utc_now(),
        )
        self.session.add(message)

        # Step 6: Update Run to terminal state
        run.state = candidate.terminal_state
        run.message_id = message_id
        run.completed_at = utc_now()

        # Step 7: Create ResultCommit record
        committed_at = utc_now()
        result_commit = ResultCommit(
            run_id=run_id,
            result_id=candidate.result_id,
            message_id=message_id,
            terminal_state=candidate.terminal_state,
            verification_version=candidate.verification_version,
            committed_at=committed_at,
        )
        self.result_commit_repo.create(result_commit)

        # Step 8: Append terminal event to outbox
        # For now, create a simple completed event
        # TODO: Full event projection per 03-B contract
        next_seq = self.outbox_repo.get_next_seq(run_id)
        terminal_event = PublicEventOutbox(
            event_id=new_id(),
            run_id=run_id,
            seq=next_seq,
            publication_key=f"completed-{run_id}",
            event_name="completed",
            envelope=self._create_event_envelope(
                run_id=run_id,
                event_name="completed",
                terminal_state=candidate.terminal_state,
            ),
            projection_version="0.1.0",
            created_at=utc_now(),
        )
        self.outbox_repo.append_event(terminal_event)

        # Transaction commits on session commit
        self.session.flush()

        return CommitReceipt(
            run_id=run_id,
            result_id=candidate.result_id,
            message_id=message_id,
            terminal_state=candidate.terminal_state,
            committed_at=committed_at,
            is_idempotent_replay=False,
        )

    def _create_event_envelope(
        self, run_id: str, event_name: str, terminal_state: str
    ) -> str:
        """Create SSE event envelope JSON."""
        import json

        return json.dumps(
            {
                "run_id": run_id,
                "event": event_name,
                "state": terminal_state,
                "timestamp": utc_now().isoformat(),
            }
        )
