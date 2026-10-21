"""Reuse the isolated source fixture, in a separate release directory."""
import verify_recall_demo as demo

demo.FOLDER = demo.ROOT / "artifacts/rehearsal-20261020"
if __name__ == "__main__":
    demo.main()
