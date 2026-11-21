"""Write the original studio render to the make.fun artifact path."""

import os
from pathlib import Path
from shutil import copyfile


def main():
    render = Path(__file__).resolve().parent / "assets" / "nimbus.jpg"
    output = Path(os.environ.get("NIMBUS_OUTPUT_DIR") or "/output")
    output.mkdir(parents=True, exist_ok=True)
    copyfile(render, output / "entry.png")


if __name__ == "__main__":
    main()
