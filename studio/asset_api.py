"""Studio routes for reviewed static assets; provider submissions are opt-in."""
import base64
import binascii
import hashlib
import io
import json
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from fastapi import Header, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import asset_pipeline as pipeline
import config
import jobs


class AssetUpload(BaseModel):
    data: str = Field(min_length=1, max_length=70 * 1024 * 1024)


class AssetPrepare(BaseModel):
    source: Literal["local", "meshy-task", "meshy-generate"] = "local"
    file: str = Field("", max_length=500)
    task_id: str = Field("", max_length=64, pattern=r"^[a-zA-Z0-9-]*$")
    task_type: Literal["image-to-3d", "text-to-3d"] = "image-to-3d"
    max_triangles: int = Field(30000, ge=100, le=100000)
    allow_cloud: bool = False
    max_credits: int = Field(0, ge=0, le=120)


class UnrealImport(BaseModel):
    file: str = Field(min_length=1, max_length=500)


def local_request(request: Request):
    try:
        allowed = ("127.0.0.1", "localhost", "::1", "testserver")
        authority = urlsplit("http://" + request.headers.get("host", request.url.netloc))
        authority.port  # Validate malformed/non-numeric port input as well.
        if authority.username or authority.password or authority.path or authority.query or authority.fragment:
            raise ValueError("invalid host authority")
        if request.url.hostname not in allowed or authority.hostname not in allowed:
            raise pipeline.AssetError("Asset tools require the local Studio host")
        origin = request.headers.get("origin")
        if origin and urlsplit(origin).netloc != authority.netloc:
            raise pipeline.AssetError("Cross-origin asset requests are not allowed")
    except (ValueError, TypeError):
        raise pipeline.AssetError("Malformed local request origin or host") from None


def register(app, *, runs, uploads, resolve, new_run, status):
    """Bind to the server's authoritative job store and constrained file roots."""
    app.mount("/asset-viewer", StaticFiles(directory=Path(__file__).parent / "vendor"),
              name="asset-viewer")
    def fail(error, code=400):
        return JSONResponse({"error": str(error)}, code)

    def worker(folder, function):
        def checkpoint():
            jobs.checkpoint(folder.name)
        try:
            checkpoint()
            status(folder, phase="generating", candidates=[])
            function(checkpoint)
        except jobs.JobCancelled:
            status(folder, phase="cancelled", error="cancelled by request")
        except jobs.JobTimeout:
            status(folder, phase="failed", error="server deadline exceeded")
        except pipeline.AssetError as exc:
            status(folder, phase="failed", error=str(exc))
        except Exception as exc:  # Fault barrier: do not leak provider text/credentials.
            status(folder, phase="failed", error=f"Asset stage failed ({type(exc).__name__})")
        finally:
            # The connection belongs to this completed worker, not future calls.
            if hasattr(jobs._LOCAL, "conn"):
                jobs._LOCAL.conn.close()
                del jobs._LOCAL.conn

    @app.get("/assets", include_in_schema=False)
    def asset_page():
        return FileResponse(Path(__file__).with_name("assets.html"))

    @app.get("/api/assets/tools")
    def asset_tools(request: Request):
        try:
            local_request(request)
            try:
                pipeline.meshy_key()
                meshy = True
            except pipeline.AssetError:
                meshy = False
            try:
                pipeline.unreal_target()
                unreal = True
            except pipeline.AssetError:
                unreal = False
            return {"meshy": meshy, "blender": config.path("blender").is_file(),
                    "unreal58": unreal, "workspace": "Dedicated BeastAssets workspace",
                    "batch_credits": 4 * pipeline.GENERATION_CREDITS,
                    "generation_model": "meshy-7.1", "generation_candidates": 4}
        except pipeline.AssetError as exc:
            return fail(exc, 403)

    @app.get("/api/assets/meshy-tasks")
    def meshy_tasks(request: Request):
        try:
            local_request(request)
            client = pipeline.Meshy()
            tasks = []
            for kind in sorted(pipeline.TASK_TYPES):
                result = client.api(f"/{kind}?limit=20&sort_by=-created_at")
                if not isinstance(result, list):
                    raise pipeline.AssetError("Meshy returned an invalid task list")
                tasks += [{"id": item["id"], "type": kind, "status": item.get("status"),
                           "created_at": item.get("created_at")}
                          for item in result if isinstance(item, dict)
                          and pipeline.TASK_ID.fullmatch(str(item.get("id", "")))]
            return {"tasks": tasks}
        except pipeline.AssetError as exc:
            return fail(exc, 503)

    @app.post("/api/assets/upload")
    def upload_asset(req: AssetUpload, request: Request):
        try:
            local_request(request)
            try:
                data = base64.b64decode(req.data, validate=True)
            except (ValueError, binascii.Error):
                raise pipeline.AssetError("Invalid asset encoding") from None
            if len(data) > pipeline.MAX_MODEL_BYTES:
                raise pipeline.AssetError("Asset exceeds 50 MiB")
            path = uploads / ("asset_" + uuid.uuid4().hex + ".glb")
            path.write_bytes(data)
            try:
                info = pipeline.validate_glb(path)
            except Exception:
                path.unlink(missing_ok=True)
                raise
            return {"file": path.name, "asset": info}
        except pipeline.AssetError as exc:
            return fail(exc)

    @app.post("/api/assets/prepare")
    def prepare_asset(req: AssetPrepare, request: Request,
                      idempotency_key: str | None = Header(None)):
        try:
            local_request(request)
            src = resolve(req.file) if req.file else None
            if req.source == "local":
                if not src or not src.is_file():
                    raise pipeline.AssetError("Local GLB not found")
                pipeline.validate_glb(src)
            elif req.source == "meshy-task":
                if not req.task_id:
                    raise pipeline.AssetError("Choose an existing Meshy task")
                pipeline.meshy_key()
            else:
                if not req.allow_cloud or req.max_credits != 120:
                    raise pipeline.AssetError("Confirm image upload and the 120-credit four-candidate batch")
                if not idempotency_key or len(idempotency_key) > 128:
                    raise pipeline.AssetError("Paid generation requires a unique idempotency key")
                if not src or not src.is_file():
                    raise pipeline.AssetError("Source image not found")
                from PIL import Image
                try:
                    with Image.open(src) as image:
                        if image.width * image.height > 16 * 1024 * 1024:
                            raise pipeline.AssetError("Source image exceeds 16 megapixels")
                        image.verify()
                except pipeline.AssetError:
                    raise
                except Exception:
                    raise pipeline.AssetError("Source must be a valid image") from None
                if src.stat().st_size > 10 * 1024 * 1024:
                    raise pipeline.AssetError("Source image exceeds 10 MiB")
                pipeline.meshy_key()
                pipeline.preflight_blender()
            params = req.model_dump()
            if src:
                params["source_sha256"] = pipeline.sha256(src)
            folder, created = new_run("Static asset handoff", "asset-pipeline", "asset", params,
                                      idempotency_key)
            if not created:
                if (jobs.get(folder.name) or {}).get("params") != params:
                    return fail("Idempotency key is bound to a different request", 409)
                return {"id": folder.name, "idempotent_replay": True}

            def execute(checkpoint):
                candidates, submitted = [], []
                count = 4 if req.source == "meshy-generate" else 1
                client = pipeline.Meshy() if req.source != "local" else None
                if req.source == "meshy-generate":
                    balance = client.api("/balance", checkpoint=checkpoint)
                    if not isinstance(balance, dict) or balance.get("balance", 0) < 120:
                        raise pipeline.AssetError("Meshy balance is below the approved 120-credit batch")
                for i in range(1, count + 1):
                    checkpoint()
                    slot = folder / f"candidate_{i}"
                    slot.mkdir()
                    original = slot / "source.glb"
                    task_id = req.task_id
                    if req.source == "meshy-generate":
                        fingerprint = hashlib.sha256((params["source_sha256"] + str(i)).encode()).hexdigest()
                        intent = {"slot": i, "fingerprint": fingerprint, "model": "meshy-7.1",
                                  "estimated_credits": 30, "state": "submission_outcome_unknown",
                                  "submitted_tasks": submitted}
                        image_bytes = src.read_bytes()
                        checkpoint()
                        if hashlib.sha256(image_bytes).hexdigest() != params["source_sha256"]:
                            raise pipeline.AssetError("Source image changed before provider submission")
                        with Image.open(io.BytesIO(image_bytes)) as image:
                            normalized = io.BytesIO()
                            image.convert("RGBA" if image.mode == "RGBA" else "RGB").save(normalized, "PNG")
                            image_bytes = normalized.getvalue()
                        intent["uploaded_image_sha256"] = hashlib.sha256(image_bytes).hexdigest()
                        # Write intent immediately before POST. No submission retry.
                        pipeline.atomic_json(folder / "provider-state.json", intent)
                        result = client.api("/image-to-3d", data={
                            "image_url": "data:image/png;base64," + base64.b64encode(image_bytes).decode(),
                            "ai_model": "meshy-7.1", "should_texture": True,
                            "enable_pbr": True, "texture_resolution": "2k",
                            "geometry_resolution": "standard", "should_remesh": False,
                            "target_formats": ["glb"]}, checkpoint=checkpoint)
                        task_id = result.get("result") if isinstance(result, dict) else None
                        if not isinstance(task_id, str) or not pipeline.TASK_ID.fullmatch(task_id):
                            raise pipeline.AssetError("Submission outcome unknown; reconcile Meshy tasks before retrying")
                        submitted.append(task_id)
                        intent.update(state="submitted", task_id=task_id, submitted_tasks=submitted)
                        pipeline.atomic_json(folder / "provider-state.json", intent)
                    if client:
                        kind = "image-to-3d" if req.source == "meshy-generate" else req.task_type
                        while True:
                            checkpoint()
                            task = client.task(kind, task_id, checkpoint)
                            if task.get("status") == "SUCCEEDED":
                                break
                            if task.get("status") in ("FAILED", "CANCELED"):
                                raise pipeline.AssetError("Meshy task failed or was canceled")
                            if req.source == "meshy-task":
                                raise pipeline.AssetError("Existing Meshy task is not complete")
                            for _ in range(20):
                                checkpoint()
                                time.sleep(.25)
                        client.download(task, original, checkpoint)
                    else:
                        shutil.copyfile(src, original)
                        if pipeline.sha256(original) != params["source_sha256"]:
                            raise pipeline.AssetError("Source GLB changed before preparation")
                    status(folder, phase="generating", asset_stage=f"Blender · candidate {i}/{count}",
                           candidates=candidates)
                    receipt = pipeline.prepare(original, slot, req.max_triangles, checkpoint)
                    receipt.update(source_kind=req.source, task_id=task_id or None,
                                   task_type=req.task_type if client else None,
                                   review_state="draft", rights="Owner must confirm reuse rights")
                    pipeline.atomic_json(slot / "asset-receipt.json", receipt)
                    candidates.append({"i": i, "state": "draft for review", "glb": True,
                                       "file": f"candidate_{i}/model.glb",
                                       "preview": f"candidate_{i}/preview.png",
                                       "receipt": receipt["blender"]})
                    status(folder, phase="generating", candidates=candidates)
                checkpoint()
                status(folder, phase="done", asset_pipeline=True, candidates=candidates,
                       final=candidates[0]["file"], glb=True, asset_stage="Ready for your review")

            threading.Thread(target=worker, args=(folder, execute), daemon=True).start()
            return {"id": folder.name, "idempotent_replay": False}
        except pipeline.AssetError as exc:
            return fail(exc)

    @app.post("/api/assets/unreal")
    def unreal_import(req: UnrealImport, request: Request):
        try:
            local_request(request)
            src = resolve(req.file)
            if not src or not src.is_file():
                raise pipeline.AssetError("Reviewed GLB not found")
            pipeline.validate_glb(src)
            pipeline.unreal_target()
            params = {**req.model_dump(), "source_sha256": pipeline.sha256(src)}
            reference = req.file.replace("\\", "/")
            prefix = str(Path(reference).parent).replace("\\", "/") if reference.startswith("runs/") else "uploads"
            downloads = [{"label": name, "url": f"/{prefix}/{name}"} for name in
                         (src.name, "asset.fbx", "asset.blend", "preview.png", "asset-receipt.json")
                         if (src.parent / name).is_file()]
            receipt_path = src.parent / "blender-receipt.json"
            prepared = json.loads(receipt_path.read_text()) if receipt_path.is_file() else {}
            selection = {"reference": reference, "url": f"/{prefix}/{src.name}",
                         "preview": f"/{prefix}/preview.png" if (src.parent / "preview.png").is_file() else "",
                         "downloads": downloads, "blender": prepared}
            folder, _ = new_run("Unreal 5.8 static asset import", "unreal58", "asset-unreal", params)

            def execute(checkpoint):
                staged = folder / "source.glb"
                shutil.copyfile(src, staged)
                if pipeline.sha256(staged) != params["source_sha256"]:
                    raise pipeline.AssetError("Source changed before Unreal import")
                status(folder, phase="generating", asset_stage="Unreal 5.8 · import and readback",
                       selected_asset=selection)
                receipt = pipeline.import_unreal(staged, folder, checkpoint)
                checkpoint()
                status(folder, phase="done", asset_pipeline=True, ue_asset=receipt["destination"],
                       asset_stage="Imported and reloaded in Unreal 5.8", candidates=[],
                       unreal_receipt=receipt)

            threading.Thread(target=worker, args=(folder, execute), daemon=True).start()
            return {"id": folder.name}
        except pipeline.AssetError as exc:
            return fail(exc)
