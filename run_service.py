from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv


PROJECT_ROOT = Path(__file__).resolve().parent
VENV_DIR = PROJECT_ROOT / ".venv"
REQUIREMENTS_FILE = PROJECT_ROOT / "requirements.txt"
MIN_PYTHON = (3, 10)
REQUIRED_MODULES = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "stable_whisper": "stable-ts",
    "praatio": "praatio",
    "multipart": "python-multipart",
}


def venv_python_path() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def current_python_too_old() -> bool:
    return sys.version_info < MIN_PYTHON


def current_python_label() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def current_missing_modules() -> list[str]:
    missing: list[str] = []
    for module_name in REQUIRED_MODULES:
        if importlib.util.find_spec(module_name) is None:
            missing.append(module_name)
    return missing


def python_has_required_modules(python_executable: Path) -> bool:
    probe = """
import importlib.util
import sys
modules = ['fastapi', 'uvicorn', 'stable_whisper', 'praatio', 'multipart']
missing = [name for name in modules if importlib.util.find_spec(name) is None]
sys.exit(0 if not missing else 1)
""".strip()
    result = subprocess.run(
        [str(python_executable), "-c", probe],
        cwd=PROJECT_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def require_python_version() -> None:
    if current_python_too_old():
        wanted = ".".join(str(part) for part in MIN_PYTHON)
        raise RuntimeError(
            f"Python {wanted}+ is required. Found {current_python_label()} at {sys.executable}."
        )


def require_ffmpeg() -> str:
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path
    raise RuntimeError(
        "ffmpeg was not found in PATH. Install it first, for example: sudo apt install ffmpeg"
    )


def print_status() -> None:
    ffmpeg_path = shutil.which("ffmpeg") or "missing"
    venv_python = venv_python_path()
    print(f"project_root={PROJECT_ROOT}")
    print(f"python={sys.executable}")
    print(f"python_version={current_python_label()}")
    print(f"ffmpeg={ffmpeg_path}")
    print(f"venv={VENV_DIR}")
    print(f"venv_python_exists={venv_python.exists()}")
    print(f"current_missing_modules={','.join(current_missing_modules()) or 'none'}")
    if venv_python.exists():
        venv_ready = python_has_required_modules(venv_python)
        print(
            "venv_missing_modules="
            + ("none" if venv_ready else "missing")
        )


def run_checked(command: list[str]) -> None:
    print("+", " ".join(command))
    try:
        subprocess.run(command, cwd=PROJECT_ROOT, check=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Command failed with exit code {exc.returncode}: {' '.join(command)}") from exc


def ensure_venv() -> Path:
    python_executable = venv_python_path()
    if python_executable.exists():
        return python_executable

    print(f"Creating virtual environment in {VENV_DIR}")
    builder = venv.EnvBuilder(with_pip=True, clear=False, symlinks=os.name != "nt")
    builder.create(VENV_DIR)

    if not python_executable.exists():
        raise RuntimeError(f"Virtual environment creation failed: {python_executable} not found.")
    return python_executable


def install_dependencies() -> Path:
    require_python_version()
    require_ffmpeg()
    if not REQUIREMENTS_FILE.exists():
        raise RuntimeError(f"Missing requirements file: {REQUIREMENTS_FILE}")

    python_executable = ensure_venv()
    run_checked([str(python_executable), "-m", "pip", "install", "--upgrade", "pip", "wheel", "setuptools"])
    run_checked([str(python_executable), "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)])
    return python_executable


def reexec_into(python_executable: Path, args: list[str]) -> None:
    os.execv(str(python_executable), [str(python_executable), str(Path(__file__).resolve()), *args])


def ensure_runtime(auto_install: bool, forwarded_args: list[str]) -> None:
    require_python_version()
    require_ffmpeg()

    missing = current_missing_modules()
    if not missing:
        return

    package_names = ", ".join(REQUIRED_MODULES[name] for name in missing)
    venv_python = venv_python_path()

    if not auto_install:
        raise RuntimeError(
            "Missing Python packages in the current interpreter: "
            f"{package_names}. Run `python3 run_service.py install` first."
        )

    venv_ready = venv_python.exists() and python_has_required_modules(venv_python)
    if not venv_ready:
        install_dependencies()

    reexec_into(venv_python, forwarded_args)


def serve(host: str, port: int, reload_enabled: bool, auto_install: bool) -> None:
    forwarded_args = ["serve", "--host", host, "--port", str(port)]
    if reload_enabled:
        forwarded_args.append("--reload")
    if auto_install:
        forwarded_args.append("--auto-install")

    ensure_runtime(auto_install=auto_install, forwarded_args=forwarded_args)

    import uvicorn

    uvicorn.run(
        "service:app",
        host=host,
        port=port,
        reload=reload_enabled,
        workers=1,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap and run the lyric alignment API from a drop-in folder."
    )
    subparsers = parser.add_subparsers(dest="command")

    install_parser = subparsers.add_parser("install", help="Create .venv and install Python dependencies.")
    install_parser.add_argument(
        "--print-status",
        action="store_true",
        help="Print environment status after installation.",
    )

    doctor_parser = subparsers.add_parser("doctor", help="Print environment checks.")
    doctor_parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when checks fail.",
    )

    serve_parser = subparsers.add_parser("serve", help="Start the HTTP API.")
    serve_parser.add_argument("--host", default="0.0.0.0")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument("--reload", action="store_true")
    serve_parser.add_argument(
        "--auto-install",
        action="store_true",
        help="Create .venv and install requirements automatically when needed.",
    )

    raw_args = sys.argv[1:] or ["serve"]
    args = parser.parse_args(raw_args)
    command = args.command or "serve"

    try:
        if command == "install":
            install_dependencies()
            if args.print_status:
                print_status()
            else:
                print(f"Installed dependencies into {VENV_DIR}")
            return 0

        if command == "doctor":
            missing_modules = current_missing_modules()
            ffmpeg_path = shutil.which("ffmpeg")
            print_status()
            if args.strict and (missing_modules or not ffmpeg_path or current_python_too_old()):
                return 1
            return 0

        serve(
            host=args.host,
            port=args.port,
            reload_enabled=args.reload,
            auto_install=args.auto_install,
        )
        return 0
    except RuntimeError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
