"""FastAPI entry point for the Algofusion production UI."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from api.algofusion_api.models import FieldUpdateRequest
from api.algofusion_api.services import ArtifactService


def create_app() -> FastAPI:
    """Create the HTTP API without binding it to a concrete server."""
    app = FastAPI(
        title="Algofusion UI API",
        version="0.1.0",
        description="Operational API over Algofusion pipeline artifacts with safe review drafts.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    service = ArtifactService.from_env()

    @app.get("/")
    def root() -> dict[str, str]:
        return {"service": "Algofusion UI API", "docs": "/docs", "health": "/api/health"}

    @app.get("/api/health")
    def health() -> dict[str, object]:
        return service.health()

    @app.get("/api/stats")
    def stats() -> dict[str, object]:
        return service.stats()

    @app.get("/api/documents")
    def documents(
        status: str | None = Query(default=None),
        doc_type: str | None = Query(default=None, alias="type"),
        limit: int = Query(default=250, ge=1, le=1000),
    ) -> dict[str, object]:
        return {"documents": service.list_documents(status=status, doc_type=doc_type, limit=limit)}

    @app.get("/api/documents/{document_id}")
    def document(document_id: str) -> dict[str, object]:
        doc = service.get_document(document_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="Document not found")
        return doc

    @app.get("/api/documents/{document_id}/artifacts")
    def artifacts(document_id: str) -> dict[str, object]:
        tree = service.artifacts(document_id)
        if tree is None:
            raise HTTPException(status_code=404, detail="Document not found")
        return tree

    @app.get("/api/documents/{document_id}/artifact")
    def artifact_file(document_id: str, path: str = Query(...)) -> FileResponse:
        file_path = service.resolve_artifact_path(document_id, path)
        if file_path is None or not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=404, detail="Artifact not found")
        return FileResponse(file_path)

    @app.get("/api/documents/{document_id}/artifact-text")
    def artifact_text(document_id: str, path: str = Query(...)) -> JSONResponse:
        preview = service.artifact_text(document_id, path)
        if preview is None:
            raise HTTPException(status_code=404, detail="Artifact text is unavailable")
        return JSONResponse(preview)

    @app.post("/api/documents/{document_id}/review")
    def save_review(document_id: str, payload: FieldUpdateRequest) -> dict[str, object]:
        result = service.save_review_draft(document_id, payload.fields)
        if result is None:
            raise HTTPException(status_code=404, detail="Document not found")
        return result

    @app.get("/api/export/queue")
    def export_queue() -> dict[str, object]:
        return service.export_queue()

    @app.get("/api/events")
    def events(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, object]:
        return {"events": service.events(limit=limit)}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.algofusion_api.main:app", host="0.0.0.0", port=8000, reload=True)

