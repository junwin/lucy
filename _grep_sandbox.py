import subprocess, sys
result = subprocess.run(['grep', '-E', 'sandbox_execute', 'logs/my_log_file.log'], capture_output=True, text=True)
if result.returncode == 0:
    print(result.stdout[-3000:])
elif result.returncode == 1:
    print("No matches found for 'sandbox_execute'")
else:
    print(f"Error: {result.stderr}")
    sys.exit(result.returncode)
