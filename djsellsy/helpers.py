import logging
import pprint

from .client import SellsyClient


logger = logging.getLogger('vendors.dj_sellsy')


class SellsyApiObject:

    sellsy_id = None
    api_object_content = {}

    _client = None

    def __init__(self, sellsy_id, fetch=True):
        """
        Init the APIObject. If `fetch` is `True`, a call to the Sellsy API will automatically
        be performed in order to fetch the object info.
        """
        self._client = SellsyClient()

        self.sellsy_id = sellsy_id
        if fetch:
            self._fetch_api_object()

    def fetch(self):
        """Fetch the api object content and put it into `api_object_content`."""
        logger.debug(
            f"Fetching Sellsy API object of type '{self.__class__}' "
            f"with id: {self.sellsy_id} ..."
        )
        self.api_object_content = self._fetch_api_object()

    def _fetch_api_object(self):
        """Perform a call to the API to fetch the API object."""
        raise NotImplementedError

    @classmethod
    def create(cls, data):
        """Create"""
        raise NotImplementedError


class Client(SellsyApiObject):
    """Help to manipulate clients on Sellsy."""

    def _fetch_api_object(self):
        return self._client.get_client_by_id(self.sellsy_id)

    @classmethod
    def create(cls, data, fetch=True):
        """
        Create a new client on sellsy.

        Note: at least a `name` key is mandatory into `data`.

        Parameters
        ----------
        data: dict
        fetch: bool, default: `True`
            If `True`, fetch the api in order to return a synchronized Client api object instance.
        """
        logger.info(
            f"Creating Sellsy API object of type '{cls.__class__}' "
            f"from data: {pprint.pformat(data, indent=4)} ..."
        )
        sellsy_client = SellsyClient()
        # FIXME: Error handling.
        sellsy_id = sellsy_client.create_company(data)

        return cls(sellsy_id=sellsy_id, fetch=fetch)
