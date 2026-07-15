"""Paste clipboard images as temporary file paths, and text normally."""

from datetime import datetime
from pathlib import Path

from kitty.boss import Boss
from kittens.tui.handler import result_handler


IMAGE_TYPES = (
    ("image/png", ".png"),
    ("image/jpeg", ".jpg"),
    ("image/webp", ".webp"),
    ("image/gif", ".gif"),
    ("image/tiff", ".tiff"),
    ("image/bmp", ".bmp"),
)


def main(args: list[str]) -> None:
    pass


@result_handler(no_ui=True)
def handle_result(
    args: list[str], answer: None, target_window_id: int, boss: Boss
) -> None:
    window = boss.window_id_map.get(target_window_id)
    if window is None:
        return

    available = set(boss.clipboard.get_available_mime_types_for_paste())
    image_type = next(
        ((mime, suffix) for mime, suffix in IMAGE_TYPES if mime in available),
        None,
    )

    if image_type is not None:
        mime, suffix = image_type
        data = boss.clipboard.get_mime_data(mime)
        if data:
            temp_dir = Path("/tmp/codex-clipboard")
            temp_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            image_path = temp_dir / f"clipboard-{timestamp}{suffix}"
            with image_path.open("xb") as image_file:
                image_file.write(data)
            image_path.chmod(0o600)
            window.paste_text(str(image_path))
            return

    # Preserve Kitty's normal behavior when the clipboard contains text.
    if window.send_paste_event():
        return
    text = boss.clipboard.get_text()
    if text:
        window.paste_with_actions(text)
