from django.core.files.storage import storages


def get_archive_storage():
    """Resolve the dedicated archive storage lazily after Django is configured."""
    return storages["archive"]
