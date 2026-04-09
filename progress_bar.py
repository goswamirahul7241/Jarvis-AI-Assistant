import time
import sys


def progress_bar(iterations=10, delay=0.5):
    for i in range(iterations):
        progress = int((i + 1) / iterations * 20)
        bar = "=" * progress + "-" * (20 - progress)
        percent = int((i + 1) / iterations * 100)
        sys.stdout.write(f"\r[{bar}] {percent}% ({i + 1}/{iterations})")
        sys.stdout.flush()
        time.sleep(delay)
    print()


if __name__ == "__main__":
    progress_bar(10, 0.5)
