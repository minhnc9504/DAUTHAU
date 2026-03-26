"""
main.py - Launcher chính cho hệ thống gợi ý gói thầu.

Usage:
    python main.py              # auto run (tương đương run)
    python main.py setup        # cài dependencies
    python main.py ingest       # đọc CSV, tạo curated parquet
    python main.py build-index  # build profiles + hybrid index
    python main.py rebuild      # ingest + build-index
    python main.py serve        # mở Streamlit UI
    python main.py run          # auto check + serve
    python main.py run --no-serve  # auto check, không mở UI
    python main.py status       # in trạng thái artifact
"""
import argparse
import importlib
import json
import os
import subprocess
import sys
import io
from datetime import datetime
from pathlib import Path

# Fix UTF-8 output on Windows console
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Đảm bảo src/ nằm trong PYTHONPATH
SRC_ROOT = Path(__file__).parent / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def _pip_install() -> None:
    """Cài dependencies từ requirements.txt."""
    req_file = Path(__file__).parent / "requirements.txt"
    if not req_file.exists():
        print(f"[Setup] Không tìm thấy {req_file}, bỏ qua.")
        return
    print("[Setup] Đang cài dependencies...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
        check=True,
    )
    print("[Setup] Hoàn tất.")


def _ensure_deps() -> None:
    """Import kiểm tra các thư viện bắt buộc."""
    required = ["streamlit", "pandas", "sklearn", "numpy", "xlsxwriter", "pyarrow"]
    missing = []
    for lib in required:
        try:
            importlib.import_module(lib)
        except ImportError:
            missing.append(lib)
    if missing:
        print(f"[Warning] Thiếu thư viện: {missing}")
        print("Chạy: python main.py setup")
        raise SystemExit(1)


def _run_ingest(settings_module, *, quiet: bool = False) -> None:
    """Chạy ingest pipeline."""
    import functools

    _print = functools.partial(print, flush=True)

    from data.ingest import ingest

    settings = settings_module.SETTINGS
    settings.ensure_dirs()

    if not Path(settings.raw_csv_path).exists():
        print(f"[Ingest] LỖI: Không tìm thấy file CSV: {settings.raw_csv_path}")
        raise SystemExit(1)

    if not quiet:
        _print("[Ingest] Bắt đầu pipeline...")
    ingest(
        str(settings.raw_csv_path),
        str(settings.curated_dir),
        verbose=not quiet,
    )
    _save_metadata(settings, tender_count=_get_row_count(settings.tender_snapshot_path))


def _run_build_index(settings_module, *, quiet: bool = False) -> None:
    """Build company profiles và hybrid retrieval index."""
    import functools

    _print = functools.partial(print, flush=True)

    def log(msg: str) -> None:
        if not quiet:
            _print(msg)

    from data.store import load_contractor_history, load_tender_snapshot
    from ranking.hybrid import HybridRanker
    from ranking.lexical import LexicalIndexer
    from ranking.semantic import SemanticIndexer
    from services.profile import build_all_profiles

    settings = settings_module.SETTINGS
    settings.ensure_dirs()

    if not settings.contractor_history_path.exists():
        print("[Build] LỖI: Thiếu contractor_history. Chạy `python main.py ingest` trước.")
        raise SystemExit(1)
    if not settings.tender_snapshot_path.exists():
        print("[Build] LỖI: Thiếu tender_snapshot. Chạy `python main.py ingest` trước.")
        raise SystemExit(1)

    log("[Build] Bắt đầu build index...")

    # Load data
    history_df = load_contractor_history(settings.contractor_history_path)
    snapshot_df = load_tender_snapshot(settings.tender_snapshot_path)

    # Build profiles
    log("[Build] Đang xây dựng company profiles...")
    build_all_profiles(history_df, settings.company_profiles_path)

    # Build lexical index
    log("[Build] Đang xây dựng lexical index...")
    lexical = LexicalIndexer.build(snapshot_df)
    lexical.save(settings.lexical_index_path)
    log(f"  [Build] Lexical matrix shape: {lexical.matrix.shape}")

    # Build semantic index
    log("[Build] Đang xây dựng semantic index...")
    semantic = SemanticIndexer.build(snapshot_df, settings.semantic_model_name)
    if semantic.ready:
        semantic.save(settings.semantic_index_path)
    log(f"  [Build] Semantic ready: {semantic.ready}")

    # Save hybrid index as combined package
    import joblib
    joblib.dump(
        {
            "lexical": {
                "vectorizer": lexical.vectorizer,
                "matrix": lexical.matrix,
                "tender_ids": lexical.tender_ids,
            },
            "semantic": {
                "model_name": semantic.model_name,
                "embeddings": semantic.embeddings,
                "tender_ids": semantic.tender_ids,
                "ready": semantic.ready,
            },
            "version": "2.0",
        },
        settings.hybrid_index_path,
    )
    log(f"[Build] Đã lưu hybrid_index -> {settings.hybrid_index_path}")

    # Update metadata
    meta = {
        "built_at": datetime.now().isoformat(),
        "lexical_vocab_size": int(lexical.matrix.shape[1]),
        "lexical_doc_count": int(lexical.matrix.shape[0]),
        "semantic_ready": semantic.ready,
        "semantic_model": semantic.model_name if semantic.ready else None,
        "semantic_embedding_dim": int(semantic.embeddings.shape[1]) if semantic.ready else None,
        "profiles_count": _get_row_count(settings.company_profiles_path),
        "tender_count": _get_row_count(settings.tender_snapshot_path),
        "history_count": _get_row_count(settings.contractor_history_path),
    }
    settings.metadata_path.parent.mkdir(parents=True, exist_ok=True)
    with open(settings.metadata_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    log(f"[Build] Đã lưu metadata -> {settings.metadata_path}")
    log("[Build] Hoàn tất.")


def _get_row_count(path: Path) -> int:
    if path is None or not path.exists():
        return 0
    try:
        import pandas as pd
        return int(pd.read_parquet(path).shape[0])
    except Exception:
        return 0


def _save_metadata(settings, **kwargs) -> None:
    meta = {
        "built_at": datetime.now().isoformat(),
        "raw_csv": str(settings.raw_csv_path),
        "curated_dir": str(settings.curated_dir),
        "artifacts_dir": str(settings.artifacts_dir),
    }
    meta.update(kwargs)
    settings.metadata_path.parent.mkdir(parents=True, exist_ok=True)
    with open(settings.metadata_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


def _needs_rebuild(settings) -> bool:
    """Kiểm tra xem artifact có cần rebuild không."""
    raw = Path(settings.raw_csv_path)
    curated = Path(settings.curated_dir)
    artifacts = Path(settings.artifacts_dir)

    if not raw.exists():
        return False

    # Nếu thiếu curated hoặc artifacts -> cần rebuild
    if not curated.exists() or not artifacts.exists():
        return True

    # So sánh timestamp
    raw_mtime = raw.stat().st_mtime
    curated_mtime = 0
    artifacts_mtime = 0

    ch = settings.contractor_history_path
    if ch.exists():
        curated_mtime = max(curated_mtime, ch.stat().st_mtime)
    ts = settings.tender_snapshot_path
    if ts.exists():
        curated_mtime = max(curated_mtime, ts.stat().st_mtime)
    idx = settings.hybrid_index_path
    if idx.exists():
        artifacts_mtime = idx.stat().st_mtime

    return raw_mtime > curated_mtime or raw_mtime > artifacts_mtime


def _run_serve(*, quiet: bool = False) -> None:
    """Mở Streamlit UI."""
    _ensure_deps()
    src_path = str(Path(__file__).parent / "src")
    env = os.environ.copy()
    env["PYTHONPATH"] = src_path
    app_path = str(Path(__file__).parent / "src" / "ui" / "streamlit_app.py")
    cmd = [
        sys.executable, "-m", "streamlit", "run",
        "--server.headless=true",
        "--",
        app_path,
    ]
    if not quiet:
        print(f"[Serve] Đang mở Streamlit UI...")
        print(f"[Serve] PYTHONPATH={src_path}")
        print(f"[Serve] App path={app_path}")
    subprocess.run(cmd, env=env, check=True)


def _print_status(settings) -> None:
    """In trạng thái artifact."""
    print("=" * 50)
    print("TRẠNG THÁI ARTIFACT")
    print("=" * 50)

    items = [
        ("contractor_history", settings.contractor_history_path),
        ("tender_snapshot", settings.tender_snapshot_path),
        ("company_profiles", settings.company_profiles_path),
        ("hybrid_index", settings.hybrid_index_path),
        ("metadata", settings.metadata_path),
    ]

    for name, path in items:
        status = "✅" if path.exists() else "❌"
        mtime = ""
        if path.exists():
            t = datetime.fromtimestamp(path.stat().st_mtime)
            mtime = f" ({t.strftime('%Y-%m-%d %H:%M')})"
        print(f"  {status} {name}{mtime}")

    if settings.metadata_path.exists():
        try:
            with open(settings.metadata_path) as f:
                meta = json.load(f)
            print("\nMetadata:")
            for k, v in meta.items():
                print(f"  - {k}: {v}")
        except Exception:
            pass

    sem_ready = False
    idx = settings.hybrid_index_path
    if idx.exists():
        try:
            import joblib
            data = joblib.load(idx)
            sem_ready = data.get("semantic", {}).get("ready", False)
        except Exception:
            pass

    print(f"\nSemantic ready: {'✅' if sem_ready else '❌'}")
    print(f"Semantic model: {settings.semantic_model_name}")

    weights = settings.get_normalized_weights(sem_ready)
    print("\nTrọng số (normalized):")
    for k, v in weights.items():
        print(f"  - {k}: {v:.4f}")

    print("=" * 50)


def main() -> None:
    parser = argparse.ArgumentParser(description="Hệ thống gợi ý gói thầu VietinBank v2.0")
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=["setup", "ingest", "build-index", "rebuild", "serve", "run", "status"],
        help="Lệnh cần chạy (mặc định: run)",
    )
    parser.add_argument(
        "--no-serve",
        action="store_true",
        help="Khi dùng 'run': chỉ xử lý pipeline, không mở UI",
    )
    args = parser.parse_args()

    # Import settings sau khi đã setup sys.path
    from settings import SETTINGS as settings
    # settings = settings_module

    if args.command == "setup":
        _pip_install()
        return

    if args.command == "ingest":
        _run_ingest(settings_module)
        return

    if args.command == "build-index":
        _run_build_index(settings_module)
        return

    if args.command == "rebuild":
        _run_ingest(settings_module)
        _run_build_index(settings_module)
        return

    if args.command == "serve":
        _run_serve()
        return

    if args.command == "run":
        print("=" * 50, flush=True)
        print("🚀 ĐANG KHỞI ĐỘNG HỆ THỐNG GỢI Ý GÓI THẦU", flush=True)
        print("=" * 50, flush=True)

        if _needs_rebuild(settings):
            print("🔄 Bước 1: Đang đồng bộ dữ liệu từ CSV...", flush=True)
            print("🚀 Đang đọc dữ liệu gốc...", flush=True)
            from data.ingest import _detect_encoding

            _run_ingest(settings_module, quiet=True)
            enc_used = _detect_encoding(str(settings.raw_csv_path))
            print(f"✅ Đọc thành công với bảng mã: {enc_used}", flush=True)
            print("✅ Đã chuyển đổi dữ liệu sạch sang Parquet thành công!", flush=True)
            print("🧠 Bước 2: Đang cập nhật bộ não AI...", flush=True)
            print("🧠 AI đang học dữ liệu mới (Huấn luyện lại)...", flush=True)
            _run_build_index(settings_module, quiet=True)
            print(
                "✅ Model đã được huấn luyện thành công và lưu vào thư mục 'models'!",
                flush=True,
            )
            print("✅ Cập nhật hoàn tất!", flush=True)
        else:
            print(
                "✅ Artifact đã sẵn sàng — bỏ qua đồng bộ CSV và huấn luyện AI.",
                flush=True,
            )

        if not args.no_serve:
            print("", flush=True)
            print("🌐 Bước 3: Đang mở giao diện trên trình duyệt...", flush=True)
            print("", flush=True)
            _run_serve(quiet=True)
        else:
            print("[Run] Hoàn tất pipeline (--no-serve).", flush=True)
        return

    if args.command == "status":
        _print_status(settings)
        return


if __name__ == "__main__":
    main()
