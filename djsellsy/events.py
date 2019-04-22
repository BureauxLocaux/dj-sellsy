import json
import logging

logger = logging.getLogger('vendors.dj_sellsy')


def handle_webhook(request):

    # The Sellsy webhook transmits all data under a `notif` key in the POST data.
    raw_message = request.POST.get('notif')
    logger.debug("Received message from Sellsy webhook", raw_message)

    try:
        message = json.loads(raw_message)
    except Exception:
        logger.warning("Unable to parse Sellsy webhook message")
    else:
        return SellsyEvent(message)


class SellsyEvent:

    def __init__(self, message, **kwargs):
        pass
