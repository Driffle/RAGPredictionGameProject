"""python -m apps  starts the Floor Brief website."""

from apps.api import serve

if __name__ == "__main__":
    serve(host="0.0.0.0", port=8765)
