import io

import pytest
from PIL import Image

import image_storage
from image_storage import MAX_IMAGE_EDGE, delete_images, download_image, prepare_images, upload_images


class Upload:
    def __init__(self, name, content):
        self.name = name
        self._content = content

    def getvalue(self):
        return self._content


def image_bytes(format="PNG", size=(2200, 1100)):
    output = io.BytesIO()
    Image.new("RGB", size, "#087f8c").save(output, format=format)
    return output.getvalue()


def test_png_is_resized_and_converted_to_webp():
    prepared = prepare_images([Upload("장비 화면.png", image_bytes())])[0]
    assert prepared.original_name == "장비 화면.png"
    assert max(prepared.width, prepared.height) == MAX_IMAGE_EDGE
    with Image.open(io.BytesIO(prepared.content)) as converted:
        assert converted.format == "WEBP"


def test_rejects_more_than_two_images():
    files = [Upload(f"{index}.png", image_bytes(size=(10, 10))) for index in range(3)]
    with pytest.raises(ValueError, match="최대 2장"):
        prepare_images(files)


def test_rejects_non_image_file():
    with pytest.raises(ValueError, match="지원되는 이미지"):
        prepare_images([Upload("not-image.png", b"not an image")])


def test_local_storage_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(image_storage, "LOCAL_ROOT", tmp_path)
    monkeypatch.setenv("DATABASE_BACKEND", "sqlite")
    prepared = prepare_images([Upload("장비.png", image_bytes(size=(100, 50)))])
    metadata = upload_images(42, prepared)
    assert len(metadata) == 1
    assert metadata[0]["path"].startswith("42/")
    assert download_image(metadata[0]) == prepared[0].content
    delete_images(metadata)
    assert not list(tmp_path.rglob("*.webp"))
