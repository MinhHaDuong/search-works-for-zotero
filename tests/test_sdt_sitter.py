"""Exercise the production admission loop with deterministic asynchronous hosts."""
import subprocess
from pathlib import Path


def test_sdt_sitter_scheduler():
    root = Path(__file__).resolve().parents[1]
    subprocess.run(['node', 'tests/sdt_sitter_scheduler.mjs'], cwd=root,
                   check=True, capture_output=True, text=True, timeout=30)


def test_sdt_sitter_bootstrap_syntax():
    root = Path(__file__).resolve().parents[1]
    subprocess.run(['node', '--check', 'bench/sdt-sitter/bootstrap.js'], cwd=root,
                   check=True, capture_output=True, text=True, timeout=30)
