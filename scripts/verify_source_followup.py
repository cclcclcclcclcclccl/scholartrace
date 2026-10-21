"""Start a separate library/account sandbox using the candidate frontend."""

import verify_transfer_workflow as workflow

workflow.FOLDER = workflow.ROOT / "artifacts/source-followup-20261021/workflow"

if __name__ == "__main__":
    workflow.main()
