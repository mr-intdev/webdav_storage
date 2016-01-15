Weird N-master WebDAV

### webdav-storage

Кастомный вебдав сторадж с наипростейшей поддержкой нескольких бекендов.

## установка

```bash
INSTALLED_APPS += ('webdav_storage',)

WEBDAV_LOCATIONS = ['127.0.0.1:11211', 'https://dav1.dev.lab.sys.mail.ru/webdav/']
```

## использование

### способ №1

```python
from webdav_storage import WebDAVStorage

webdav_storage = WebDAVStorage()

image = models.ImageField('Изображение', upload_to=image_path, max_length=255, storage=webdav_storage)
```

### способ №2
```python
DEFAULT_FILE_STORAGE = 'webdav_storage.WebDAVStorage'
```
