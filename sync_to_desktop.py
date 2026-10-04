import os
import shutil
import sys

src_root = os.getcwd()
dst_root = r"C:\Users\hp\OneDrive\Desktop\New folder (5)"

print(f"Syncing from: {src_root}")
print(f"Syncing to:   {dst_root}")

os.makedirs(dst_root, exist_ok=True)

items_to_copy = [
    "app",
    "docs",
    "tests",
    "README.md",
    "EVALUATION_REPORT.md",
    "main.py",
    "requirements.txt",
    ".env.example",
    ".gitignore",
    "sync_to_desktop.py"
]

for item in items_to_copy:
    src_item = os.path.join(src_root, item)
    dst_item = os.path.join(dst_root, item)
    
    if os.path.isdir(src_item):
        if os.path.exists(dst_item):
            shutil.rmtree(dst_item)
        shutil.copytree(src_item, dst_item)
        print(f"  [DIR] Copied {item} -> {dst_item}")
    elif os.path.isfile(src_item):
        shutil.copy2(src_item, dst_item)
        print(f"  [FILE] Copied {item} -> {dst_item}")

print("Sync completed successfully!")
