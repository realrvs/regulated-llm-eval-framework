import subprocess
result = subprocess.run(
    ["python", "-m", "pytest", "--no-header", "-q"],
    capture_output=True, text=True, cwd=r"D:\downloads\AI\regulated-llm-eval"
)
with open(r"D:\downloads\AI\regulated-llm-eval\_failures.txt", "w") as f:
    for line in result.stdout.split('\n'):
        if 'FAILED' in line:
            f.write(line[:400] + '\n')
    f.write(f"\nTotal passed/failed:\n")
    for line in result.stdout.split('\n'):
        if 'passed' in line or 'failed' in line:
            f.write(line + '\n')
print("Done")
