import ast
import pathlib

FORBIDDEN_IMPORTS = {
    "socket",
    "ssl",
    "http",
    "urllib",
    "ftplib",
    "smtplib",
    "asyncio",
    "requests",
    "httpx",
}
ALLOWED_IMPORT_FROM = {
    ("verify.py", "urllib.parse"),
}


def test_no_network_imports() -> None:
    project_root = pathlib.Path(__file__).parent.parent
    targets = [
        project_root / "src" / "capsule" / "engine",
        project_root / "src" / "capsule" / "store",
    ]

    for src_dir in targets:
        assert src_dir.exists(), f"Could not find {src_dir}"
        for py_file in src_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")

            try:
                tree = ast.parse(content, filename=str(py_file))
            except SyntaxError as err:
                raise AssertionError(f"Syntax error in {py_file}: {err}") from err

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        base_name = name.name.split(".")[0]
                        assert base_name not in FORBIDDEN_IMPORTS, (
                            f"Forbidden import '{name.name}' found in {py_file}"
                        )
                elif isinstance(node, ast.ImportFrom) and node.module:
                    base_name = node.module.split(".")[0]
                    if (py_file.name, node.module) in ALLOWED_IMPORT_FROM:
                        continue
                    assert base_name not in FORBIDDEN_IMPORTS, (
                        f"Forbidden import '{node.module}' found in {py_file}"
                    )
