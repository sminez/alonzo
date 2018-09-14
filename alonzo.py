'''
A quick and dirty Monzo API for python
======================================

Get original access token from https://developers.monzo.com
Docs are found here: https://docs.monzo.com/
'''
from datetime import datetime, date, timedelta
from dateutil.parser import parse as parse_date

from requests import get, post


def rfc3339_datetime(dt):
    '''
    Convert a datetime object into an RFC3339 compliant string
    '''
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


class MonzoClient:
    '''
    A bare bones Monzo client that requires an active API token, returning
    the raw JSON responses from the API.
    '''
    base_url = 'https://api.monzo.com/{}'

    def __init__(self, token):
        self.token = token

    def _query(self, endpoint, req_func, params={}, data=None, headers=None):
        '''
        Helper function for making requests to the monzo API.
        '''
        _headers = {"Authorization": "Bearer " + self.token}

        if headers is None:
            headers = {}
        headers.update(_headers)

        resp = req_func(
            self.base_url.format(endpoint),
            params=params,
            data=data,
            headers=headers,
        )

        return resp.json()

    def _get_default_account_id(self):
        '''
        Helper for locating the first non-closed account for the user when
        one is not passed to a method requiring an account_id.
        '''
        # Take the first open account we can find
        accounts = self.list_accounts()
        for account in accounts:
            if account.is_active:
                return account.id

    def _populate_time_params(self, params, since, before):
        '''
        Correctly format the time paramaters for queries that need them.
        '''
        if since is None:
            # Default to one week ago
            since = date.today() - timedelta(days=7)

        since = rfc3339_datetime(since)
        params['since'] = since

        if before is not None:
            before = rfc3339_datetime(before)
            params['before'] = before

        return params

    def whoami(self):
        '''
        Check the token we have to determine it's properties.
        '''
        return self._query('ping/whoami', get)

    def list_accounts(self):
        '''
        List all of the accounts (open and closed) for the user associated
        with this token.
        '''
        return [
            Account._new_from_api_response(r)
            for r in self._query('accounts', get)['accounts']
        ]

    def get_balance(self, account_id=None):
        '''
        Show the balanace for the given account. Defaults to the first open
        account that the user has if none is specified.

        Note that the balance returned is in "minor units" for the currency
        in question (i.e. pence for £, cents for $ etc)
        '''
        if account_id is None:
            account_id = self._get_default_account_id()

        return self._query('balance', get, params={'account_id': account_id})

    def get_pots(self, account_id=None):
        '''
        Show all of the pots associated with a given account. Defaults to the
        first open account that the user has if none is specified.
        '''
        if account_id is None:
            account_id = self._get_default_account_id()

        return self._query('pots', get, params={'account_id': account_id})

    def list_transactions(self, account_id=None, since=None, before=None,
                          full=False):
        '''
        Show all of the transactions associated with a given account. Defaults
        to the first open account that the user has if none is specified.

        since and before should be datetime objects
        '''
        if account_id is None:
            account_id = self._get_default_account_id()

        params = {'account_id': account_id}
        if not full:
            params = self._populate_time_params(params, since, before)

        return [
            Transaction(t) for t in
            self._query('transactions', get, params=params)['transactions']
        ]


class Account:
    def __init__(self, id, description, created, account_type, active, owners):
        self.id = id
        self.description = description
        self.created = created
        self.account_type = account_type
        self.is_active = active
        self.owners = owners

    @classmethod
    def _new_from_api_response(cls, resp):

        return cls(
            id=resp['id'],
            description=resp['description'],
            created=parse_date(resp['created']),
            account_type=resp['type'],
            active=not resp['closed'],
            owners=[User(**u) for u in resp['owners']]
        )

    def __repr__(self):
        return 'Monzo Account: {}'.format(self.description)


class User:
    def __init__(self, user_id, preferred_name, preferred_first_name):
        self.user_id = user_id
        self.preferred_name = preferred_name
        self.preferred_first_name = preferred_first_name

    def __repr__(self):
        return self.preferred_name


class Transaction:
    def __init__(self, api_resp):
        self.__dict__.update(api_resp)
        # Convert times to datetime objects
        self.created = parse_date(api_resp['created'])
        # self.settled = parse_date(api_resp['settled'])
        # self.updated = parse_date(api_resp['updated'])

    def __repr__(self):
        return '({}) {}: {} {}'.format(
            self.created.strftime('%Y-%m-%d %H:%M'),
            self.description,
            self.currency,
            self.amount / 100
        )
