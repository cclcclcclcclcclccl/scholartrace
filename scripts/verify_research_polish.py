"""Isolated real-paper demonstration for question checks and comparison readiness."""

import verify_transfer_workflow as workflow

workflow.FOLDER = workflow.ROOT / "artifacts/research-polish-20261021/workflow"

if __name__ == "__main__":
    workflow.main()
