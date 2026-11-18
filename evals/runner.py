import json
from pathlib import Path


def main() -> None:
    dataset = json.loads(Path(__file__).with_name("dataset.json").read_text(encoding="utf-8"))
    print(f"Loaded {len(dataset)} evaluation cases.")
    print("This safe dataset loader does not invoke the agent or mutate database records.")
    print("Run with a non-production fixture harness to record per-case evaluator scores.")


if __name__ == "__main__":
    main()
