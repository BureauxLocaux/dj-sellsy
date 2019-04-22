import logging

from django.db import models
from django.utils.translation import ugettext_lazy as _

logger = logging.getLogger('vendors.dj_sellsy')


class SellsySyncableManager(models.Manager):

    def get_by_sellsy_id(sellsy_id):
        return self.get(sellsy_id=sellsy_id)


class SellsySyncable(models.Model):

    sellsy_id = models.IntegerField(_("Sellsy ID"),
        blank=True, null=True,
        help_text=_("The unique identifier of this object in Sellsy"),
    )

    class Meta:
        abstract = True

    def sync_from_sellsy(self):
        pass

    def sync_to_sellsy(self):
        pass
