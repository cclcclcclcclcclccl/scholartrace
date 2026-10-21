"""Reuse the real-paper walkthrough with fresh library and account isolation."""

import verify_transfer_workflow as workflow

workflow.FOLDER = workflow.ROOT / "artifacts/coverage-quality-20261020/workflow"

if __name__ == "__main__":
    workflow.main()
