# coding: utf-8
import hashlib
import os
import logging
import random
try:
    from StringIO import StringIO
except ImportError:
    from io import BytesIO as StringIO
try:
    from urlparse import urljoin
except ImportError:
    from urllib.parse import urljoin
import requests
import pycurl
from django.conf import settings
from django.core.files import File
from django.core.files.storage import Storage


logger = logging.getLogger('webdav')
DEFAULT_TIME_OUT = getattr(settings, 'WEBDAV_TIME_OUT', 15.0)


class FileReader:
    def __init__(self, fp):
        self.fp = fp
    def read_callback(self, size):
        return self.fp.read(size)


class WebDAVException(Exception):
    pass


class WebDAVStorage(Storage):
    """
    WebDAV Storage class for Django
    """
    def __init__(self, locations=settings.WEBDAV_LOCATIONS, timeout=DEFAULT_TIME_OUT):
        self._locations = locations
        self._timeout = int(timeout or DEFAULT_TIME_OUT)

    def save(self, name, content, max_length=None):
        path, file_name = os.path.split(name)
        f_name, f_extension = os.path.splitext(file_name)
        hash_name = os.path.join(path, hashlib.md5(f_name.encode("utf-8")).hexdigest() + f_extension)
        return super(WebDAVStorage, self).save(hash_name, content, max_length)

    def _get_full_path(self, location, name):
        return urljoin(location, str(name))

    def exists(self, name):

        logger.debug(u'checking existing of {0}'.format(name))

        file_found = False

        # check all dav instances for file existence,
        # if file exist in one of them then we think that file exists
        for location in self._locations:
            logger.debug(u'checking via location {0}'.format(location))
            response = requests.head(
                self._get_full_path(location, name), timeout=self._timeout)
            if response.status_code == 200:
                file_found = True
                logger.debug(u'file found')
                break

        if not file_found:
            logger.debug(u'file does not exist')

        return file_found

    def _save(self, name, content):
        logger.debug(u'saving {0}'.format(name))

        is_tmp_file = hasattr(content.file, 'temporary_file_path')
        if is_tmp_file:
            data = None
            logger.debug(u"uploading from temporary file")
        else:
            # read content into memory
            logger.debug(u"uploading from memory")
            data = content.read()

        for location in self._locations:
            logger.debug(u'saving in {0}'.format(location))

            if is_tmp_file:

                # send file without loading it in memory
                c = pycurl.Curl()
                f = content.file.temporary_file_path()
                c.setopt(c.URL, self._get_full_path(location, name))
                c.setopt(c.PUT, True)
                filesize = os.path.getsize(f)
                c.setopt(pycurl.INFILESIZE, filesize)
                c.setopt(pycurl.READFUNCTION, FileReader(open(f, 'rb')).read_callback)
                c.setopt(pycurl.TIMEOUT, self._timeout)
                c.perform()
                status_code = int(c.getinfo(c.RESPONSE_CODE))
                c.close()

            else:
                response = requests.put(
                    self._get_full_path(location, name),
                    data=data, timeout=self._timeout
                )
                status_code = response.status_code

            if status_code not in (201, 204):
                msg = u"uploading {0}: status code {1}".format(
                    self._get_full_path(location, name), status_code
                )
                logger.error(msg)
                raise WebDAVException(msg)

        logger.debug(u'{0} successfully saved'.format(name))

        return name

    def _open(self, name, mode):
        logger.debug(u'opening {0}'.format(name))
        location = random.choice(self._locations)
        logger.debug(u'getting via {0}'.format(location))
        response = requests.get(
            self._get_full_path(location, name), timeout=self._timeout)
        if response.status_code == 404 and hasattr(settings, 'WEBDAV_READ_FALLBACK'):
            location = settings.WEBDAV_READ_FALLBACK
            response = requests.get(
                self._get_full_path(location, name), timeout=self._timeout
            )
        if response.status_code != 200:
            msg = u"error getting file {0}: status code {1}".format(
                self._get_full_path(location, name), response.status_code)
            logger.error(msg)
            raise WebDAVException(msg)
        return File(StringIO(response.content))

    def delete(self, name):

        logger.debug(u'deleting {0}'.format(name))

        for location in self._locations:
            logger.debug(u'deleting in {0}'.format(location))
            response = requests.delete(
                self._get_full_path(location, name), timeout=self._timeout)
            if response.status_code not in (204,):
                msg = u"deleting {0}: status code {1}".format(
                    self._get_full_path(location, name), response.status_code)
                logger.error(msg)
                raise WebDAVException(msg)

        logger.debug(u'{0} deleted'.format(name))

    def url(self, name):
        return urljoin(settings.MEDIA_URL, name)

    def size(self, name):

        logger.debug(u'getting {0} size'.format(name))

        for location in self._locations:
            logger.debug(u'getting via {0}'.format(location))
            try:
                response = requests.head(
                    self._get_full_path(location, name), timeout=self._timeout)
            except Exception as err:
                logger.exception(err)
            else:
                return response.headers.get('Content-Length')

        logger.error(u'file size not found')

        return None
