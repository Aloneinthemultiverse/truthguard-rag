"""Runs PaddleOCR inside its own virtualenv and returns JSON on stdout.

paddlepaddle publishes no wheel for Python 3.13+, so it cannot live in the main
environment. Rather than drop the engine, it runs out-of-process in .venv-paddle
and is called as a subprocess. Nothing else in the project imports paddle.

Usage:  <.venv-paddle python> -m truthguard.paddle_worker <image_path>
Output: {"text": str, "conf": float, "engine": "paddleocr"}  or  {"error": str}
"""
import json
import sys


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "usage: paddle_worker <image_path>"}))
        return 2
    try:
        from paddleocr import PaddleOCR
        ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        result = ocr.ocr(sys.argv[1], cls=True)
        lines, confs = [], []
        for page in result or []:
            for entry in page or []:
                text, conf = entry[1][0], float(entry[1][1])
                lines.append(text)
                confs.append(conf)
        print(json.dumps({
            "text": "\n".join(lines),
            "conf": (sum(confs) / len(confs)) if confs else 0.0,
            "engine": "paddleocr",
        }))
        return 0
    except Exception as e:
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
