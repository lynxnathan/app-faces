import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_TIMEOUT_SECONDS = 60


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=RUN_TIMEOUT_SECONDS,
        env={**os.environ, "NO_COLOR": "1"},
    )


def verify_python_mutation(
    old: str,
    new: str,
    test: str,
    module_name: str = "app_faces.bundles",
    function: str = "extract_appimage",
) -> dict[str, str]:
    program = f"""
import inspect
import pytest
import importlib
module = importlib.import_module({module_name!r})
source = inspect.getsource(getattr(module, {function!r}))
assert {old!r} in source
exec(compile(source.replace({old!r}, {new!r}), '<mutation>', 'exec'), module.__dict__)
raise SystemExit(pytest.main(['-q', '--tb=short', '-p', 'no:cacheprovider', {test!r}]))
"""
    baseline = run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", test], ROOT)
    assert baseline.returncode == 0, baseline.stdout + baseline.stderr
    mutant = run([sys.executable, "-c", program], ROOT)
    assert (
        mutant.returncode == 1 and "1 failed" in mutant.stdout and "AssertionError" in mutant.stdout
    ), mutant.stdout + mutant.stderr
    return {"test": test, "baseline": "passed", "mutation": "caught by assertion"}


def verify_ip_mutation() -> dict[str, str]:
    with tempfile.TemporaryDirectory(prefix="app-faces-mutation-") as temporary:
        root = Path(temporary)
        backend = root / "backend"
        backend.mkdir()
        for directory in ("src", "tests", "migrations"):
            shutil.copytree(ROOT / "backend" / directory, backend / directory)
        (backend / "build").mkdir()
        shutil.copyfile(ROOT / "backend/build/admin.bundle.txt", backend / "build/admin.bundle.txt")
        shutil.copytree(ROOT / "app_faces/locales", root / "app_faces/locales")
        shutil.copyfile(ROOT / "backend/package.json", backend / "package.json")
        (backend / "node_modules").symlink_to(
            ROOT / "backend/node_modules", target_is_directory=True
        )
        report = backend / "result.json"
        command = [
            str(backend / "node_modules/.bin/vitest"),
            "run",
            "tests/backend.test.ts",
            "-t",
            "raw IP is absent",
            "--reporter=json",
            "--outputFile=" + str(report),
        ]
        baseline = run(command, backend)
        assert baseline.returncode == 0, baseline.stdout + baseline.stderr
        source = backend / "src/index.ts"
        original = source.read_text()
        old = 'name = textField(body["name"], "name");'
        assert original.count(old) == 1
        source.write_text(
            original.replace(
                old,
                'name = request.headers.get("CF-Connecting-IP") ?? textField(body["name"], "name");',
            )
        )
        report.unlink()
        mutant = run(command, backend)
        results = json.loads(report.read_text())
        failures = [
            case
            for suite in results["testResults"]
            for case in suite["assertionResults"]
            if case["status"] == "failed"
        ]
        assert mutant.returncode == 1 and len(failures) == 1, mutant.stdout + mutant.stderr
        assert "192.0.2.94" in str(failures[0]["failureMessages"]), failures
        return {
            "test": "raw IP absent from D1 rows",
            "baseline": "passed",
            "mutation": "caught by assertion",
        }


def main() -> None:
    results = [
        verify_python_mutation(
            "if len(desktop_names) != 1:",
            "if not desktop_names:",
            "tests/test_bundles.py::test_two_valid_desktop_entries_are_ambiguous",
        ),
        verify_python_mutation(
            "desktop_names = [",
            "subprocess.Popen([str(path)])\n        desktop_names = [",
            "tests/test_bundles.py::test_extract_uses_archive_tools_without_executing_candidate",
        ),
        verify_python_mutation(
            'if origin and (Path(origin).name != origin or origin in (".", "..")):',
            "if False:",
            "tests/test_identity.py::test_appstream_rejects_traversal_to_existing_artwork[origin]",
            "app_faces.identity",
            "_icon",
        ),
        verify_python_mutation(
            'kind == "cached" and value and Path(value).name == value',
            'kind == "cached" and value',
            "tests/test_identity.py::test_appstream_rejects_traversal_to_existing_artwork[filename]",
            "app_faces.identity",
            "_icon",
        ),
        verify_python_mutation(
            'if item.get("stat") == before and isinstance(digest, str) and len(digest) == 64:',
            "if False:",
            "tests/test_identity.py::test_fingerprint_reuses_and_invalidates",
            "app_faces.identity",
            "fingerprint",
        ),
        verify_ip_mutation(),
    ]
    report = ROOT / "state/test-mutations.json"
    report.parent.mkdir(exist_ok=True)
    report.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
