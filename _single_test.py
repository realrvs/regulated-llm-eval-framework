import subprocess
import inspect
result = subprocess.run(
    ['python', '-m', 'pytest', 'tests/e2e/test_cli_vs_library.py::TestCLIVsLibraryParity::test_cli_run_command_signature', '--no-header', '-v', '--tb=short'],
    capture_output=True, text=True, cwd=r'D:\downloads\AI\regulated-llm-eval'
)
print(result.stdout[-2000:])
print(result.stderr[-500:])
