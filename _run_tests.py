import subprocess
result = subprocess.run(
    ["python", "-m", "pytest", "-q", "--no-header",
     "tests/e2e/test_cli_vs_library.py",
     "tests/integration/test_ab.py",
     "tests/integration/test_metrics.py",
     "tests/observability/test_otel.py",
     "tests/performance/test_performance.py",
     "tests/security/test_annotation_chain.py",
     "tests/security/test_secrets.py",
     "tests/e2e/test_human_loop.py",
     "-x"],
    capture_output=True, text=True, cwd="D:\\downloads\\AI\\regulated-llm-eval"
)
print(result.stdout[-3000:] if len(result.stdout) > 3000 else result.stdout)
print(result.stderr[-1000:] if len(result.stderr) > 1000 else result.stderr)
print(f"Return code: {result.returncode}")
