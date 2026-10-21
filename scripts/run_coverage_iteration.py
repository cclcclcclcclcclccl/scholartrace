"""Repeat the exposed seven tasks; their confirmation status is historical only."""

import argparse
import asyncio
import json

import transfer_study as study


async def main(label):
    study.ARTIFACTS = study.ROOT / "artifacts/coverage-quality-20261020"
    study.write(
        study.ARTIFACTS / f"{label}-notice.json",
        {
            "notice": "重复验证已暴露的七道任务，包括此前已经运行过的三道确认题；不是新的保留集或独立准确率。",
            "code_sha256": study.code_hashes(),
            "protocol_sha256": study.digest(study.PROTOCOL),
        },
    )
    for split in ["diagnostic", "confirmation"]:
        await study.run(split, label + "-" + split, product_only=True)
    print(json.dumps({"finished": label, "new_unseen_tasks": 0}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    asyncio.run(main(parser.parse_args().label))
