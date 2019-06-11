import datetime
import logging
import pprint
import time

from django.conf import settings
from django.utils.translation import ugettext as _

import sellsy_api
from sellsy_api.errors.sellsy_exceptions import SellsyError

from . import constants

logger = logging.getLogger('vendors.dj_sellsy')


class SellsyClient:
    """
    Required settings:

    - SELLSY_CONSUMER_TOKEN
    - SELLSY_CONSUMER_SECRET
    - SELLSY_USER_TOKEN
    - SELLSY_USER_SECRET

    """
    POST_REQUEST_DELAY = 1  # in seconds

    _client = None

    _currencies_raw_data = None
    _CURRENCY_IDS = []

    _payment_dates_raw_data = None
    _PAYMENT_DATE_IDS = []

    _payment_modes_raw_data = None
    _PAYMENT_MODE_IDS = []

    _taxes_raw_data = None
    _TAX_IDS = []

    _properties_raw_data = None
    _PROPERTY_IDS = []

    _property_groups_raw_data = None
    _PROPERTY_GROUP_IDS = []

    _clients_raw_data = None
    _contacts_raw_data = None
    _products_raw_data = None

    def __init__(self, deferred_connection=False, **kwargs):
        if not deferred_connection:
            self.connect()

    def connect(self):
        self._client = sellsy_api.Client(
            settings.SELLSY_CONSUMER_TOKEN,
            settings.SELLSY_CONSUMER_SECRET,
            settings.SELLSY_USER_TOKEN,
            settings.SELLSY_USER_SECRET,
        )

    def wait(self, delay=None):
        time.sleep(delay or self.POST_REQUEST_DELAY)

    def _search(self, search_params):
        return self._client.api(
            method='%s.getList' % (search_params.get('search_type')),
            params={'search': search_params.get('search_params')},
        )

    def _get_one(self, search_params):
        return self._client.api(
            method='%s.getOne' % (search_params.get('search_type')),
            params=search_params.get('search_params'),
        )

    # Currency-related methods

    def _get_currencies_raw_data(self, force_fetch=False):
        if force_fetch or not self._currencies_raw_data:
            self._currencies_raw_data = self._client.api(method='AccountPrefs.getCurrencies')
        return self._currencies_raw_data

    def _get_currency_id(self, currency_code, force_fetch=False):
        currencies_data = self._get_currencies_raw_data(force_fetch)
        try:
            return int(
                [
                    currency['id']
                    for key, currency in currencies_data.items()
                    if key != 'defaultCurrency' and currency['name'] == currency_code
                ][0]
            )
        except IndexError:
            return None


    # Payment modes-related methods

    def _get_payment_modes_raw_data(self, force_fetch=False):
        if force_fetch or not self._payment_modes_raw_data:
            self._payment_modes_raw_data = self._client.api(method='Accountdatas.getPayMediums')
        return self._payment_modes_raw_data

    def _get_payment_mode_id(self, payment_mode_code, force_fetch=False):
        """
        Legal values for `payment_mode_code` are:

          - 'check',
          - 'transfer',
          - 'cash',
          - 'cb',
          - 'pick',
          - 'bor',
          - 'tip',
          - 'lcr',

        """
        payment_modes_data = self._get_payment_modes_raw_data(force_fetch)
        try:
            return int(
                [
                    payment_mode['id']
                    for key, payment_mode in payment_modes_data.items()
                    if (
                        payment_mode['syscode'] == payment_mode_code
                        or payment_mode['value'] == payment_mode_code
                    )
                ][0]
            )
        except IndexError:
            return None


    # Payment dates-related methods

    def _get_payment_dates_raw_data(self, force_fetch=False):
        if force_fetch or not self._payment_dates_raw_data:
            self._payment_dates_raw_data = self._client.api(
                method='Accountdatas.getPayDates',
            )['payDates']
        return self._payment_dates_raw_data

    def _get_payment_date_id(self, payment_date_code, force_fetch=False):
        """
        Legal values for `payment_date_code` are:

            - 'onorder',
            - 'endmonth',
            - '30days',
            - '45days',
            - '60days',
            - 'xdays',
            - 'deadlines',
            - 'scaled',
            - 'custom'  <-- ONLY IF A CUSTOM PAYMENT DEADLINE IS ACTIVE IN SELLSY!!!

        """
        payment_dates_data = self._get_payment_dates_raw_data(force_fetch)
        try:
            return int(
                [
                    payment_date['id']
                    for key, payment_date in payment_dates_data.items()
                    if payment_date['syscode'] == payment_date_code
                ][0]
            )
        except IndexError:
            return None


    # Properties-related methods

    def _get_properties_raw_data(self, force_fetch=False):
        if force_fetch or not self._properties_raw_data:
            self._properties_raw_data = self._client.api(
                method='CustomFields.getList',
                params={
                    'pagination': constants.PAGINATION_ALL
                }
            )['result']
        return self._properties_raw_data

    def _get_property_id(self, code, force_fetch=False):
        props_data = self._get_properties_raw_data(force_fetch)
        try:
            return int(
                [
                    prop['id'] for key, prop in props_data.items()
                    if prop['code'] == code
                ][0]
            )
        except IndexError:
            return None

    def _prepare_prop_choices(self, choices):

        # Sensible default: the first choice is default and checked

        return [
            {
                'value': choice,
                'isDefault': 'Y' if idx == 0 else 'N',
                'checked': 'Y' if idx == 0 else 'N',
            }
            for idx, choice in enumerate(choices)
        ]

    def create_property(self, code, label, obj_types, data_type, choices=None, prefs=None):
        """

        The `code` parameter should not contain underscore, only dashes.

        Legal values for `data_type`:
            'simpletext', 'richtext', 'numeric', 'amount', 'unit', 'radio', 'select', 'checkbox',
            'date', 'time', 'email', 'url', 'boolean', 'third', 'item', 'people', 'staff'

        """

        # Assign the property to the proper object type
        use_on = [
            'showIn_list',
            'showIn_filter',
        ] + [
            'useOn_%s' % obj_type.rstrip('s')
            for obj_type in obj_types
        ]

        params = {
            'code': code,
            'name': label,
            'type': data_type,
            'useOn': use_on,
        }

        # Add property preferences
        prefs = prefs or {}
        if data_type == 'amount':
            prefs.update({
                'currencyid': self._get_currency_id(settings.SELLSY_DEFAULT_CURRENCY)
            })
        params.update({'preferences': prefs})

        # Add property choices, if any
        if choices:
            params.update({'preferenceslist': self._prepare_prop_choices(choices)})

        # Create the property
        new_prop_data = self._client.api(
            method='CustomFields.create',
            params=params,
        )
        new_prop_id = new_prop_data.get('id')

        return new_prop_id

    def _prepare_prop_values(self, prop_values):
        return [
            {
                'cfid': self._get_property_id(prop_name, force_fetch=True),
                'value': prop_value,

                # TODO: Handle `currencyid` and `unitid` fields ...?
            }
            for prop_name, prop_value in prop_values.items()
            if prop_value
        ]

    def record_property_values(self, linked_type, linked_id, prop_values):
        return self._client.api(
            method='CustomFields.recordValues',
            params={
                'linkedtype': linked_type,
                'linkedid': linked_id,
                'values': self._prepare_prop_values(prop_values),
            }
        )

    def delete_property(self, code):
        prop_id = self._get_property_id(code, force_fetch=True)
        if prop_id:
            return self._client.api(
                method='CustomFields.delete',
                params={
                    'id': prop_id,
                }
            )

    def delete_all_properties(self):
        props_data = self._get_properties_raw_data(force_fetch=True)
        if props_data:
            for prop_id, prop_spec in props_data.items():
                self.delete_property(prop_spec['code'])
                self.wait()

    def delete_all_custom_properties(self):
        return self.delete_all_properties()

    def _prepare_group_prop_specs(self, props):
        return [
            {
                'cfid': str(self._get_property_id(prop, force_fetch=True) or prop),
                'rank': str(idx),
            }
            for idx, prop in enumerate(props)
        ]

    def _get_property_groups_raw_data(self, force_fetch=False):
        if force_fetch or not self._property_groups_raw_data:
            self._property_groups_raw_data = self._client.api(
                method='CustomFields.getGroupsList',
                params={
                    'pagination': constants.PAGINATION_ALL
                }
            )['result']
        return self._property_groups_raw_data

    def _get_property_group_id(self, code, force_fetch=False):
        groups_data = self._get_property_groups_raw_data(force_fetch)
        try:
            return int(
                [
                    group['id'] for key, group in groups_data.items()
                    if group['code'] == code
                ][0]
            )
        except IndexError:
            return None

    def update_property_group(self, code, label, group_id=None, props=None):
        """
        Update a property group on sellsy.

        Cf: https://api.sellsy.fr/documentation/methodes#customfieldsgroupupdate

        Parameters
        ----------
        code: str
            The code of the group on sellsy.
        label: str
        group_id: int (optional)
            The id of the group on sellsy. Could be `None` if `code` is given.
        props: list
        """
        if not group_id and not code:
            raise ValueError("At least group_id or code must been given.")

        if not group_id:
            group_id = self._get_property_group_id(code, force_fetch=True)

        params = {
            'id': group_id,
            'code': code,
            'name': label,
        }
        if props:
            params['customFields'] = self._prepare_group_prop_specs(props)

        return self._client.api(method='CustomFields.updateGroup', params=params)

    def create_property_group(self, code, label, props):
        """

        The `code` parameter should not contain underscore, only dashes.

        """
        return self._client.api(
            method='CustomFields.createGroup',
            params={
                'code': code,
                'name': label,
                'customFields': self._prepare_group_prop_specs(props),
            }
        )

    def delete_property_group(self, code):
        group_id = self._get_property_group_id(code, force_fetch=True)
        if group_id:
            return self._client.api(
                method='CustomFields.deleteGroup',
                params={
                    'groupid': group_id,
                }
            )

    def delete_all_property_groups(self):
        groups_data = self._get_property_groups_raw_data(force_fetch=True)
        if groups_data:
            for group_id, group_spec in groups_data.items():
                self.delete_property_group(group_spec['code'])
                self.wait()

    def delete_all_custom_property_groups(self):
        return self.delete_all_property_groups()

    # Product-related methods

    def _get_products_raw_data(self, force_fetch=False, product_type=constants.PRODUCT_TYPE_ITEM):
        if force_fetch or not self._products_raw_data:
            self._products_raw_data = self._client.api(
                method='Catalogue.getList',
                params={
                    'type': product_type,
                    'pagination': constants.PAGINATION_ALL
                }
            )['result']
        return self._products_raw_data

    def _prepare_product_data(self, product_data):

        # If there is no trade name, set to name.
        if 'tradename' not in product_data:
            product_data['tradename'] = product_data['name']

        # If there is no unit name, set to "unité".
        if 'unit' not in product_data:
            product_data['unit'] = "unité"

        # If there is no tax info, use default (in settings, fallback is 20%).
        if 'taxid' not in product_data:
            vat_rate = getattr(settings, 'SELLSY_DEFAULT_VAT_RATE', 20)
            vat_rate_id = self._get_tax_id(vat_rate)
            product_data['taxid'] = vat_rate_id

        # If there is no activity info, set to 'Y' (aka True).
        if 'actif' not in product_data:
            product_data['actif'] = 'Y'

        return product_data

    def create_product(self, name, description, price,
                       extra_fields=None, custom_fields=None,
                       product_type=constants.PRODUCT_TYPE_ITEM):

        product_data = {
            'name': name,
            'notes': description,
            'unitAmount': price,
        }
        if extra_fields:
            product_data.update(extra_fields)

        product_data = self._prepare_product_data(product_data)

        new_product_data = self._client.api(
            method='Catalogue.create',
            params={
                'type': product_type,
                product_type: product_data,
            }
        )
        # print(new_product_data)
        new_product_id = new_product_data['%s_id' % product_type]

        # ... and now fill in the new product's custom fields, if any.
        if custom_fields:
            self.record_property_values(product_type, new_product_id, custom_fields)

        return new_product_id

    def get_product_by_id(self, product_id):
        pass

    def get_product_by_sku(self, product_sku):
        pass

    def update_product_data(self, product_data):
        pass

    def delete_product(self, product_id, product_type=constants.PRODUCT_TYPE_ITEM):
        return self._client.api(
            method='Catalogue.delete',
            params={
                'type': product_type,
                'id': product_id,
            }
        )

    def delete_all_products(self):
        all_products_data = self._get_products_raw_data()
        for _, product_data in all_products_data.items():
            product_id = product_data['id']
            self.delete_product(product_id)

    def get_all_products(self, product_type=constants.PRODUCT_TYPE_ITEM):
        all_products_data = self._get_products_raw_data(product_type=product_type)
        return [all_products_data[key] for key in all_products_data]

    # Client-related methods

    def _get_clients_raw_data(self, force_fetch=False):
        if force_fetch or not self._clients_raw_data:
            self._clients_raw_data = self._client.api(
                method='Client.getList',
                params={
                    'pagination': constants.PAGINATION_ALL
                }
            )['result']
        return self._clients_raw_data

    def _create_client(self, client_type, client_data):

        # We build the parameters to create the new client...
        params = {'third': client_data.get('third')}
        params['third']['type'] = client_type

        if 'contact' in client_data:
            params.update({'contact': client_data.get('contact')})
        if 'address' in client_data:
            params.update({'address': client_data.get('address')})

        # ... create it in Sellsy...
        new_client_data = self._client.api(
            method='Client.create',
            params=params
        )
        new_client_id = new_client_data.get('client_id')

        # ... and now fill in the new client's custom fields, if any.
        if 'custom' in client_data:
            third_type = 'client' if client_type == constants.CLIENT_TYPE_CORPORATION else 'people'
            self.record_property_values(third_type, new_client_id, client_data['custom'])

        return new_client_id

    # TODO: This is sharing a lot of code with _create_client.
    def _update_client(self, client_type, client_id, client_data):

        # We build the parameters to update the client...
        params = {
            'clientid': client_id,
            'third': client_data.get('third'),
        }
        params['third']['type'] = client_type

        if 'contact' in client_data:
            params.update({'contact': client_data.get('contact')})
        if 'address' in client_data:
            params.update({'address': client_data.get('address')})

        # ... update it in Sellsy ...
        response_data = self._client.api(
            method='Client.update',
            params=params
        )
        # FIXME: Should we handle the response?
        logger.debug(response_data)

        # ... and now fill in the new client's custom fields, if any.
        if 'custom' in client_data:
            third_type = 'client' if client_type == constants.CLIENT_TYPE_CORPORATION else 'people'
            self.record_property_values(third_type, client_id, client_data['custom'])

        return client_id

    # FIXME: Maybe it should be renamed `create_client`
    def create_company(self, company_data):
        return self._create_client(constants.CLIENT_TYPE_CORPORATION, company_data)

    def update_company(self, company_id, company_data):
        return self._update_client(
            client_type=constants.CLIENT_TYPE_CORPORATION,
            client_id=company_id,
            client_data=company_data,
        )

    def create_company_contact(self, company_id, contact_data):
        """
        Create a contact and associate it to the client with the given company_id.

        Cf: https://api.sellsy.fr/documentation/methodes#clientsaddcontact

        Parameters
        ----------
        company_id
        contact_data: dict
            Same dict as for `create_contact`.
        """

        # Create the new contact and associate it to the client.
        new_contact_id = self._client.api(
            method='Client.addContact',
            params={
                'clientid': company_id,
                # FIXME: Document this.
                'contact': contact_data['contact'],
            }
        )

        # Register its custom properties.
        if 'custom' in contact_data:
            third_type = 'people'
            self.record_property_values(third_type, new_contact_id, contact_data['custom'])

        if 'address' in contact_data:
            self._client.api(
                method='Addresses.create',
                params={
                    'linkedtype': 'people',
                    'linkedid': new_contact_id,
                    **contact_data.get('address'),
                }
            )

        return new_contact_id

    def create_contact(self, contact_data):
        return self._create_client(constants.CLIENT_TYPE_PERSON, contact_data)

    def get_client_by_id(self, client_id):
        """
        Get a client by its id.

        If no client is matching with the given `client_id`, `None` will be returned.
        """
        try:
            return self._get_one({
                'search_type': constants.SEARCH_TYPE_CLIENTS,
                'search_params': {
                    'clientid': client_id,
                }
            })
        except SellsyError as e:
            logger.error(
                "Cannot find a client on sellsy with the given client id.",
                extra={
                    'client_id': client_id,
                    'exception': e,
                },
            )
            return None

    def search_clients_by_name(self, name):
        return self._search({
            'search_type': constants.SEARCH_TYPE_CLIENTS,
            'search_params': {
                'name': name,
            }
        })

    def _prepare_search_prop_value(self, prop_value):
        try:
            int_value = int(prop_value)
        except ValueError:
            return prop_value
        else:

            # For a numeric search value, we must pass a dict: `{'start': value, 'stop': value}`.
            return {
                'start': int_value,
                'stop': int_value,
            }

    def search_clients_by_property(self, prop_name, prop_value):
       return self._search({
            'search_type': constants.SEARCH_TYPE_CLIENTS,
            'search_params': {
                'customfields': [
                    {
                        'cfid': self._get_property_id(prop_name),
                        'value': self._prepare_search_prop_value(prop_value),
                    },
                ]
            }
        })['result']

    def get_client_id_by_property_value(self, prop_name, prop_value):
        clients_data = self.search_clients_by_property(prop_name, prop_value)
        num_results = len(clients_data)
        if num_results == 0:
            return None
        elif num_results > 1:
            raise ValueError("Multiple clients exist with this property value")
        else:
            return int(list(clients_data['result'].keys())[0])

    def get_client_property_value(self, data, prop_name):

        # We start by looking into the standard fields.
        try:
            return data[prop_name]
        except KeyError:
            pass

        # Nope. Let's check the custom fields then.
        custom_fields = data.get('customfields')
        for custom_field in custom_fields:
            if custom_field.get('code') == prop_name:
                value = (
                    custom_field.get('boolval')
                    or custom_field.get('decimalval')
                    or custom_field.get('formatted_value')
                    or custom_field.get('numericval')
                    or custom_field.get('stringval')
                    or custom_field.get('textval')
                    or custom_field.get('timestampval')
                )
                if value:
                    return value

        # Nope, not found
        return None

    def delete_client(self, client_id):
        return self._client.api(
            method='Client.delete',
            params={
                'clientid': client_id,
            }
        )

    def _check_standard_or_custom_field(self, data, key, value):
        """
        Checks whether field named `key` has value `value`.
        Checks in both standard and custom fields.

        """

        # We start by checking the standard fields.
        if data.get(key) == value:
            return True

        # Then we iterate through the custom fields.
        custom_fields = data.get('customfields')
        for custom_field in custom_fields:
            if custom_field.get('code') == key:
                return (
                    custom_field.get('boolval') == value
                    or custom_field.get('decimalval') == value
                    or custom_field.get('formatted_value') == value
                    or custom_field.get('numericval') == value
                    or custom_field.get('stringval') == value
                    or custom_field.get('textval') == value
                    or custom_field.get('timestampval') == value
                )

        # Nope, not found
        return False

    def delete_all_clients(self, having=None):
        all_clients = self._get_clients_raw_data(force_fetch=True)
        if not all_clients:
            return

        having = having or {}

        clients_to_delete = {
            client_id: client_data
            for client_id, client_data in all_clients.items()
            if all([
                self._check_standard_or_custom_field(client_data, key, value)
                for key, value in having.items()
            ])
        }

        for client_id in clients_to_delete:
            self.delete_client(client_id)


    # Address-related methods

    def create_address(self, client_id, address_data, as_main=True):
        return self._client.api(
            method='Addresses.create',
            params={
                'linkedtype': 'third',
                'linkedid': client_id,
                'isMain': 'Y' if as_main else 'N',
                'name': address_data.get('address_name', _("Main address")),
                'part1': address_data.get('address'),
                'part2': address_data.get('address2'),
                'zip': address_data.get('zip_code'),
                'town': address_data.get('city'),
                'countrycode': address_data.get('country_code'),
            }
        )

    def get_customer_addresses(self, client_id):
        pass

    def get_customer_main_address(self, client_id):
        pass


    # Bank account-related methods

    def create_bank_account(self, client_id, account_data):
        return self._client.api(
            method='BankAccount.create',
            params={
                'bankAccount': {
                    'linkedtype': 'third',
                    'linkedid': client_id,
                    'label': _("Main bank account"),
                    'isEnabled': 'Y',
                    'hasiban': 'Y',
                    'bic': account_data.get('bic'),
                    'iban': account_data.get('iban'),
                    'sepa_authorizationNumber': account_data.get('sepa_authorization_number'),
                    'sepa_transmitterNationalNumber': account_data.get('sepa_transmitter_national_number'),  # noqa
                    'sepa_signaturemandat': account_data.get('sepa_mandate_signature_ts'),
                }
            }
        )

    def get_client_bank_accounts(self, client_id):
        pass

    def get_client_main_bank_account(self, client_id):
        pass


    # Invoice-related methods

    def _get_taxes_raw_data(self, force_fetch=False):
        if force_fetch or not self._taxes_raw_data:
            self._taxes_raw_data = self._client.api(method='Accountdatas.getTaxes')
        return self._taxes_raw_data

    def _get_tax_id(self, tax_value, force_fetch=False):

        # Use an int for `tax_value` whenever possible
        int_tax_value = int(tax_value)
        if int_tax_value == tax_value:
            tax_value = int_tax_value

        taxes_data = self._get_taxes_raw_data(force_fetch)
        try:
            return int(
                [
                    tax['id'] for key, tax in taxes_data.items()
                    if not key.startswith('default') and tax['value'] == str(tax_value)
                ][0]
            )
        except IndexError:
            return None

    def get_document_by_id(self, document_type, document_id):
        return self._client.api(
            method='Document.getOne',
            params={
                'doctype': document_type,
                'docid': document_id,
            }
        )

    def _prepare_document_rows(self, rows_data, append_sum_row=True):
        prepared_rows = []

        for row_data in rows_data:

            row_type = row_data.get('row_type', None)
            if row_type and row_type != 'once':
                # FIXME: This method dont support other row types.
                prepared_rows.append({
                    **row_data,
                    'row_taxid': self._get_tax_id(row_data['tax_rate']),  # TODO: or default?
                })
                continue

            prepared_row = {
                'row_type': 'once',
                'row_name': row_data['title'],
                'row_notes': row_data['description'],
                'row_unitAmount': row_data['unit_price'],
                'row_qt': row_data['quantity'],
                'row_taxid': self._get_tax_id(row_data['tax_rate']),  # TODO: or default?

                # 'row_purchaseAmount': row_data['total_price'],
            }
            if 'discount' in row_data:
                prepared_row.update({
                    'row_discount': row_data['discount'],
                    'row_discountUnit': row_data['discount_unit'],
                })
            if 'comment' in row_data:
                prepared_row.update({
                    'row_comment': row_data['comment'],
                })

            prepared_rows.append(prepared_row)

        if append_sum_row:
            prepared_rows.append({'row_type': 'sum'})

        return prepared_rows

    def _create_document(self, document_type, document_data):
        try:
            client_id = document_data['client_id']
        except KeyError:
            raise ValueError("You must provide a `client_id` to create a document.")

        try:
            rows_data = document_data['rows']
        except KeyError:
            raise ValueError("You must provide `rows` to create a document.")

        document_params = {
            'doctype': document_type,
            'thirdid': document_data['client_id'],
        }
        if 'parent_id' in document_data:
            document_params.update({
                'parentId': document_data['parent_id']
            })
        if 'number' in document_data:
            document_params.update({
                'ident': document_data['number']
            })
        if 'date' in document_data:
            document_params.update({
                'displayedDate': int(document_data['date'])
            })
        if 'title' in document_data:
            document_params.update({
                'subject': document_data['subject']
            })
        if 'notes' in document_data:
            document_params.update({
                'notes': document_data['notes']
            })
        if 'discount' in document_data:
            document_params.update({
                'globalDiscount': document_data['discount'],
                'globalDiscountUnit': document_data['discount_unit'],
            })
        if 'tags' in document_data:
            document_params.update({
                'tags': document_data['tags'],
            })
        # FIXME: Document this? Add an explicit parameter to the method?
        if 'payment_modes' in document_data:
            payment_modes = document_data['payment_modes']
            document_params.update({
                'payMediums': [
                    self._get_payment_mode_id(payment_mode) for payment_mode in payment_modes
                ],
            })

        paydate_params = None
        if 'paydate' in document_data:
            paydate_params = document_data['paydate']

        row_params = self._prepare_document_rows(rows_data)

        params = {
            'document': document_params,
            'row':row_params,
        }
        if paydate_params is not None:
            paydate_params['id'] = self._get_payment_date_id(paydate_params['id'])
            params.update({
                'paydate': paydate_params,
            })

        # pp = pprint.PrettyPrinter(indent=4)
        # pp.pprint(params)

        new_document_data = self._client.api(
            method='Document.create',
            params=params,
        )
        new_document_id = new_document_data.get('doc_id')

        # ... and now fill in the new document's custom fields, if any.
        if 'custom' in document_data:
            self.record_property_values('document', new_document_id, document_data['custom'])

        return new_document_id, self.get_document_by_id(document_type, new_document_id)

    def create_creditnote(self, credit_note_data):
        return self._create_document(constants.DOCUMENT_TYPE_CREDIT_NOTE, credit_note_data)

    def create_proforma(self, proforma_data):
        return self._create_document(constants.DOCUMENT_TYPE_PROFORMA, proforma_data)

    def create_invoice(self, invoice_data):
        return self._create_document(constants.DOCUMENT_TYPE_INVOICE, invoice_data)

    def create_invoice_from_proforma(self, proforma_id):
        proforma = self.get_document_by_id(constants.DOCUMENT_TYPE_PROFORMA, proforma_id)
        proforma_rows = proforma.get('map').get('rows')

        invoice_rows = []

        for proforma_row_id, proforma_row in proforma_rows.items():

            # Skip stupid rows which are not dicts
            try:
                proforma_row.get
            except AttributeError:
                continue

            # Skip rows that do not contain actual product data
            if proforma_row.get('type') != 'once':
                continue

            row_title = proforma_row.get('name')
            row_description = proforma_row.get('notes')
            row_unit_price = float(proforma_row.get('unitAmount'))
            row_quantity = int(float(proforma_row.get('qt')))
            row_tax_rate = float(proforma_row.get('taxrate'))
            row_discount = float(proforma_row.get('discount'))
            if row_discount:
                row_discount_unit = int(float(proforma_row.get('discountUnit')))

            invoice_row = {
                'title': row_title,
                'description': row_description,
                'unit_price': row_unit_price,
                'quantity': row_quantity,
                'tax_rate': row_tax_rate,
            }
            if row_discount and row_discount_unit:
                invoice_row.update({
                    'discount': row_discount,
                    'discount_unit': row_discount_unit,
                })

            invoice_rows.append(invoice_row)

        invoice_data = {
            'client_id': proforma.get('thirdid'),
            'parent_id': proforma_id,
            'date': datetime.datetime.strptime(proforma.get('displayedDate'), '%d/%m/%Y').timestamp(),
            'tags': ','.join([tag_spec['word'] for tag_id, tag_spec in proforma.get('tags').items()]),
            'rows': invoice_rows,
            'discount': proforma.get('globalDiscount'),
            'discount_unit': proforma.get('globalDiscountUnit'),

            # TODO: more info? at least the payment date(s)...
        }
        return self.create_invoice(invoice_data)

    def validate_invoice(self, invoice_id, invoice_ts=None):
        params = {
            'docid': invoice_id
        }
        if invoice_ts:
            params.update({'date': invoice_ts})

        return self._client.api(
            method='Document.validate',
            params=params,
        )

    def _update_document_status(self, document_type, document_id, new_status):
        if new_status not in constants.VALID_DOCUMENT_STATUSES:
            raise ValueError("'%s' is not a valid %s status." % (
                new_status, document_type
            ))

        return self._client.api(
            method='Document.updateStep',
            params={
                'docid': document_id,
                'document': {
                    'doctype': document_type,
                    'step': new_status,
                }
            }
        )

    def update_creditnote_status(self, creditnote_id, new_status):
        return self._update_document_status(
            constants.DOCUMENT_TYPE_CREDIT_NOTE, creditnote_id, new_status
        )

    def update_proforma_status(self, proforma_id, new_status):
        return self._update_document_status(
            constants.DOCUMENT_TYPE_PROFORMA, proforma_id, new_status
        )

    def update_invoice_status(self, invoice_id, new_status):
        return self._update_document_status(
            constants.DOCUMENT_TYPE_INVOICE, invoice_id, new_status
        )


    # Payment-related methods

    def create_payment(self, payment_data, document_type=constants.DOCUMENT_TYPE_INVOICE):

        params = {
            'date': payment_data['date'],  # TODO: maybe do the timestamp conversion here
                                           #  for a better Developer eXperience?

            'amount': payment_data['amount'],
            'medium': self._get_payment_mode_id(payment_data['mode']),
        }
        if 'reference' in payment_data:
            params.update({
                'ident': payment_data.get('reference')
            })
        if 'deadline_id' in payment_data:
            params.update({
                'deadlineid': [payment_data.get('deadline_id')]
            })

        invoice_id = payment_data.get('invoice_id', None)
        if invoice_id:

            # This payment is related to an invoice.
            method = 'Document.createPayment'
            params.update({
                'doctype': document_type,
                'docid': invoice_id,
            })
            params = {'payment': params}

        else:
            """
            I believe we don't need that implementation *right now* so it'll have to wait.

            'params' => [
                'type'          => {{type}},
                'currencyid'    => {{currencyid}},
                'linkedid'      => {{linkedid}},
                'mediumid'      => {{mediumid}},
                'inBank'        => {{inBank}},
                'bank'      => [
                    'id'        => {{bankId}},
                    'date'      => {{bankDate}}
                ]
            ]

            {{type}}        Oui                             enum('debit', 'credit')     Aucun   Type du paiement
            {{currencyid}}  Oui                             int                         Aucun   Devise associée au paiement
            {{linkedid}}    Oui                             int                         Aucun   Identifiant du client/fournisseur associé au paiement
            {{mediumid}}    Oui                             int                         Aucun   Identifiant du moyen de paiement associé au paiement
            {{inBank}}      Non                             enum('Y', 'N')              N       Spécifie si le paiement a été remis en banque
            {{bankId}}      Non, sauf si {{inBank}} = Y     int                         Aucun   Identifiant du compte bancaire associé à la remise en banque
            {{bankDate}}    Non, sauf si {{inBank}} = Y     int (timestamp)             Aucun   Date de la remise en banque

            """
            method = 'Payments.create'
            params.update({

                # TODO?

            })

        # pp = pprint.PrettyPrinter(indent=4)
        # pp.pprint(params)

        new_payment_data = self._client.api(method=method, params=params)
        new_payment_id = new_payment_data.get('payid')

        return new_payment_id
