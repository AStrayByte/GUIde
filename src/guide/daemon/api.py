"""The HTTP surface. Small, and versioned in the path because it is a contract.

Two clients, one API: the browser page and the ``guide`` CLI. Nothing else will
ever call it, because nothing else can reach it — the daemon binds ``127.0.0.1``
and there is no auth precisely because there is no one else on the socket.

Note what the request models do *not* contain. Blocks, fields, ``meta`` and
every value in an answer are ``Any``: the daemon stores and counts, it never
interprets. Modelling them here would break additive-only minors the first time
an agent used a block type newer than the installed daemon.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from guide import API_PREFIX, API_VERSION, FORMAT_VERSION, __version__
from guide.errors import BatchNotFound, IncompatibleVersion, InvalidBatch

from .service import Daemon

router = APIRouter(prefix=API_PREFIX)


def daemon_of(request: Request) -> Daemon:
    """The :class:`Daemon` this app was built around."""
    return request.app.state.daemon


class CardAnswer(BaseModel):
    """One card's answer, as the page reports it.

    ``degraded`` and ``viewer_version`` come from the viewer because only the
    viewer knows them: whether *this* renderer could draw every block on the
    card, and which renderer it was. They are what let a reading agent discount
    an answer given on partial evidence.
    """

    values: dict[str, Any] = Field(default_factory=dict)
    degraded: bool = False
    viewer_version: str | None = None


class Completion(BaseModel):
    """The Done button, and its undo.

    ``degraded_cards`` is the viewer's full list at the moment Done is pressed,
    and it catches what per-card reports structurally cannot: a card blocked by
    an unsupported *required* field can never be answered, so it never produces
    an answer record, so it could never appear in the derived list — even though
    it is exactly the card ``docs/versioning.md`` most wants flagged.
    """

    complete: bool = True
    degraded_cards: list[str] = Field(default_factory=list)


# -- Meta -----------------------------------------------------------------


@router.get("/meta")
def meta(request: Request) -> dict[str, Any]:
    """Identify this daemon.

    Doubles as the health probe and as the "is that a GUIde daemon on port
    7777, or something else entirely?" check that the port scan depends on.

    ``home`` is part of that identity. ``$GUIDE_HOME`` can point two processes at
    two different stores, and a CLI that attached to a daemon serving somebody
    else's inbox would push into it and then report nothing waiting.
    """
    daemon = daemon_of(request)
    return {
        "name": "guide",
        "version": __version__,
        "format_version": FORMAT_VERSION,
        "api_version": API_VERSION,
        "home": str(daemon.store.home),
        "batches": len(daemon.store.ids()),
        "listeners": daemon.events.subscriber_count,
    }


# -- Batches --------------------------------------------------------------


@router.post("/batches", status_code=201)
async def push_batch(request: Request, document: Annotated[Any, Body()]) -> dict[str, Any]:
    """Accept a batch from an agent session.

    The body is the batch document itself, unwrapped. ``id`` is minted here and
    any id in the body is ignored, so the pushing session never has to invent a
    collision-free one.
    """
    daemon = daemon_of(request)
    try:
        batch = daemon.push(document)
    except InvalidBatch as exc:
        raise HTTPException(422, str(exc)) from exc
    except IncompatibleVersion as exc:
        raise HTTPException(409, str(exc)) from exc

    waiting = sum(not summary.complete for summary in daemon.store.summaries())
    return {
        "id": batch["id"],
        "cards": len(batch["cards"]),
        "waiting": waiting,
        "url": f"/?batch={batch['id']}",
    }


@router.get("/batches")
def list_batches(request: Request) -> list[dict[str, Any]]:
    """The inbox: every batch in the store, oldest first."""
    return [summary.as_dict() for summary in daemon_of(request).store.summaries()]


@router.get("/batches/{batch_id}")
def get_batch(request: Request, batch_id: str) -> dict[str, Any]:
    """One batch document, exactly as it was stored."""
    try:
        return daemon_of(request).store.read_batch(batch_id)
    except BatchNotFound as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/batches/{batch_id}/answers")
def get_answers(request: Request, batch_id: str) -> dict[str, Any]:
    """The current answers document for a batch."""
    try:
        return daemon_of(request).store.read_answers(batch_id)
    except BatchNotFound as exc:
        raise HTTPException(404, str(exc)) from exc


@router.put("/batches/{batch_id}/answers/{card_id}")
async def put_card_answer(
    request: Request, batch_id: str, card_id: str, answer: CardAnswer
) -> dict[str, Any]:
    """Record one card's answer. Called on every click and every keystroke.

    Idempotent, and an empty ``values`` un-answers the card, so the page never
    has to reason about whether a change is a create or an update.
    """
    daemon = daemon_of(request)
    try:
        answers = await daemon.record(
            batch_id,
            card_id,
            answer.values,
            degraded=answer.degraded,
            viewer_version=answer.viewer_version,
        )
    except (BatchNotFound, InvalidBatch) as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"stats": answers["stats"], "updated_at": answers["updated_at"]}


@router.post("/batches/{batch_id}/complete")
async def complete_batch(
    request: Request, batch_id: str, completion: Completion
) -> dict[str, Any]:
    """Flip ``complete`` — the single thing ``guide wait`` blocks on."""
    try:
        answers = await daemon_of(request).set_complete(
            batch_id,
            complete=completion.complete,
            degraded_cards=completion.degraded_cards,
        )
    except BatchNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"complete": answers["complete"], "stats": answers["stats"]}


@router.delete("/batches/{batch_id}", status_code=204)
async def remove_batch(request: Request, batch_id: str, archive: bool = False) -> Response:
    """Delete a batch, or move it to ``~/.guide/archive/`` with ``?archive=true``.

    Delete is the default because batches may hold client data, and the safe
    default for data you did not mean to keep is not keeping it.
    """
    try:
        await daemon_of(request).remove(batch_id, archive=archive)
    except BatchNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    return Response(status_code=204)


# -- Live updates ---------------------------------------------------------


@router.get("/events")
async def events(request: Request) -> StreamingResponse:
    """Server-sent events: batches arriving, answers landing, batches finishing.

    Every frame is a hint to refresh rather than a delta to apply, so a page
    that missed one while the laptop was asleep still converges.
    """
    return StreamingResponse(
        daemon_of(request).events.stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


# -- Lifecycle ------------------------------------------------------------


@router.post("/shutdown", status_code=202)
def shutdown(request: Request) -> JSONResponse:
    """Stop the daemon, after this response has been written.

    ``guide stop`` calls this. The signal goes out in a background task so the
    client gets a clean answer rather than a dropped connection, and it is a
    signal rather than a server handle so the same path works however uvicorn
    was started.
    """
    return JSONResponse(
        status_code=202,
        content={"stopping": True},
        background=BackgroundTask(request.app.state.request_shutdown),
    )
