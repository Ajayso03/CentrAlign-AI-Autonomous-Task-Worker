"""
Main CLI & Server Entrypoint for CentrAlign Autonomous AI Task Worker.
"""

import os
import sys
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print("=================================================================")
    print("      CentrAlign AI ? Autonomous Task Worker Console")
    print(f"      Running on: http://localhost:{port}")
    print("      ERP Portal: http://localhost:8000/sandbox/portal")
    print("=================================================================\n")
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
