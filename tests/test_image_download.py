import json
import uuid
from pathlib import Path
from src.http_endpoints.upload_endpoints import get_image_download_impl


class Config:
    def __init__(self, root): self.root = root
    def get(self, key, default=None):
        return {'storage_root_path': str(self.root), 'storage_namespace': 'data'}.get(key, default)


def saved_image(tmp_path):
    image_id = str(uuid.uuid4())
    directory = tmp_path / 'data' / 'images' / 'john'
    directory.mkdir(parents=True)
    image = directory / (image_id + '.png')
    from PIL import Image
    Image.new('RGB', (32, 32), 'red').save(image, format='PNG')
    (directory / (image_id + '.json')).write_text(json.dumps({'id': image_id, 'account': 'john', 'mime_type': 'image/png'}))
    return image_id, image


def test_owned_image_resolves(tmp_path):
    image_id, image = saved_image(tmp_path)
    path, body, status = get_image_download_impl(Config(tmp_path), 'john', image_id)
    assert status == 200 and path == str(image)
    assert body['mime_type'] == 'image/png'


def test_other_account_has_no_access(tmp_path):
    image_id, _ = saved_image(tmp_path)
    assert get_image_download_impl(Config(tmp_path), 'arla', image_id)[2] == 404


def test_invalid_id_and_account_fail(tmp_path):
    assert get_image_download_impl(Config(tmp_path), 'john', '../file')[2] == 400
    assert get_image_download_impl(Config(tmp_path), '../john', str(uuid.uuid4()))[2] == 400


def test_symlink_outside_storage_is_rejected(tmp_path):
    image_id, image = saved_image(tmp_path)
    image.unlink()
    image.symlink_to('/etc/hosts')
    assert get_image_download_impl(Config(tmp_path), 'john', image_id)[2] == 400


def test_metadata_account_must_match(tmp_path):
    image_id, image = saved_image(tmp_path)
    image.with_suffix('.json').write_text(json.dumps({'id': image_id, 'account': 'arla', 'mime_type': 'image/png'}))
    assert get_image_download_impl(Config(tmp_path), 'john', image_id)[2] == 400
