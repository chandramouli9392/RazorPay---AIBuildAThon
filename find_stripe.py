import os

keywords = ["stripe", "STRIPE", "Stripe"]
matches = []

for root, _dirs, files in os.walk("."):
    if ".venv" in root or "__pycache__" in root or ".git" in root:
        continue
    for f in files:
        path = os.path.join(root, f)
        try:
            with open(path, encoding="utf-8", errors="ignore") as fp:
                for idx, line in enumerate(fp, 1):
                    if any(k in line for k in keywords):
                        matches.append(f"{path}:{idx}: {line.strip()[:100]}")
        except Exception:
            pass

print(f"Total occurrences found: {len(matches)}")
for m in matches:
    print(m)
