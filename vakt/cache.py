"""
Caching mechanisms for vakt
"""

import logging
from functools import lru_cache

from .util import Subject, Observer


__all__ = [
    'EnfoldCache',
    'GuardCache',
]


log = logging.getLogger(__name__)


class EnfoldCache:
    """
    Wraps all underlying storage interface calls with a cache that is represented by another storage.
    When `init` arg is True populates cache with all the existing policies at the startup.
    Typical usage might be:
    storage = EnfoldCache(MongoStorage(...), cache=MemoryStorage(), populate=True).
    """

    def __init__(self, storage, cache, populate=False):
        self.storage = storage
        self.cache = cache
        self.populate_step = 1000
        if populate:
            self.populate()

    def populate(self):
        limit = self.populate_step
        offset = 0
        while True:
            policies = self.storage.get_all(limit, offset)
            if not policies:
                break
            for p in policies:
                self.cache.add(p)
            offset = limit + 1

    def add(self, policy):
        """
        Cache storage `add`
        """
        # we aren't catching any exceptions - just letting them pass
        self.storage.add(policy)
        self.cache.add(policy)

    def get(self, uid):
        """
        Cache storage `get`
        """
        policy = self.cache.get(uid)
        if policy:
            return policy
        log.warning(
            '%s cache miss for get Policy with UID=%s. Trying to get it from backend storage',
            type(self).__name__, uid
        )
        return self.storage.get(uid)

    def get_all(self, limit, offset):
        """
        Cache storage `get_all`
        """
        result = self.cache.get_all(limit, offset)
        if result:
            return result
        return self.storage.get_all(limit, offset)

    def find_for_inquiry(self, inquiry, checker=None):
        """
        Cache storage `find_for_inquiry`
        """
        result = self.cache.find_for_inquiry(inquiry, checker)
        if result:
            return result
        return self.storage.find_for_inquiry(inquiry, checker)

    def update(self, policy):
        """
        Cache storage `update`
        """
        self.storage.update(policy)
        self.cache.update(policy)

    def delete(self, uid):
        """
        Cache storage `delete`
        """
        self.storage.delete(uid)
        self.cache.delete(uid)


class GuardCache(Observer):
    """
    Caches hits of `find_for_inquiry` for given Inquiry and Checker.
    In case of a cache hit returns the cached boolean result, in case of a cache miss goes to a Storage and
    and memorizes its result for future calls with the same Inquiry and Checker.
    If underlying Storage notifies it that policies set has anyhow changed, invalidates all the cached results.
    """
    def __init__(self, storage, maxsize=1024, cache_type='memory'):
        self.storage = ObservableStorage(storage)
        self.cache_type = cache_type
        self.maxsize = maxsize
        self.cache = self._create_cache()

    def start(self):
        self.storage.add_listener(self)
        return self.storage

    def _create_cache(self):
        if self.cache_type == 'memory':
            self.storage.find_for_inquiry = lru_cache(self.maxsize)(self.storage.find_for_inquiry)
        else:
            raise Exception('Unknown cache type for GuardCache')

    def update(self):
        self._create_cache()


class ObservableStorage(Subject):
    """
    Wraps and implements mutation part of Storage interface.
    Notifies observers when mutation method is called on Storage.
    """
    def __init__(self, storage):
        self.storage = storage
        super().__init__()

    def add(self, policy):
        res = self.storage.add(policy)
        self.notify()
        return res

    def update(self, policy):
        res = self.storage.update(policy)
        self.notify()
        return res

    def delete(self, uid):
        res = self.storage.delete(uid)
        self.notify()
        return res

    def get(self, uid):
        return self.storage.get(uid)

    def get_all(self, limit, offset):
        return self.storage.get_all(limit, offset)

    def find_for_inquiry(self, inquiry, checker=None):
        return self.storage.find_for_inquiry(inquiry, checker)
