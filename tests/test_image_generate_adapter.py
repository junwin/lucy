import base64
import io
from PIL import Image
from types import SimpleNamespace
from unittest.mock import Mock
from galet.imagegen_dto import ImageGenResponse, ImageResult
from galet_tools.tools.image_generate_handler import ImageGenerateHandler as SharedHandler
from src.handlers.image_generate_handler import ImageGenerateHandler


def test_lucy_adapter_uses_shared_handler_and_storage(tmp_path):
    values = {'storage_root_path': str(tmp_path), 'storage_namespace': 'data'}
    config = SimpleNamespace(get=lambda key: values.get(key))
    handler = ImageGenerateHandler(config)
    assert isinstance(handler, SharedHandler)
    assert handler._storage_resolver.storage_base_dir() == str(tmp_path / 'data')
    handler._image_api = Mock()
    output = io.BytesIO()
    Image.new('RGB', (32, 32), 'red').save(output, format='PNG')
    handler._image_api.generate_image.return_value = ImageGenResponse([ImageResult(b64_json=base64.b64encode(output.getvalue()).decode())])
    result = handler.execute({'prompt': 'A hill', 'model': 'gpt-image-1'}, account_name='john')
    assert result['ok']
    handler._image_api.generate_image.assert_called_once_with(model='gpt-image-1', prompt='A hill', size='1024x1024', quality='standard', n=1)
