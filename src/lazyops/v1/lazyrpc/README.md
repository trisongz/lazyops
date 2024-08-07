# LazyFastAPI

Modified from https://github.com/smagafurov/fastapi-jsonrpc

Basically:

```python

# Has explicit module imports so that all the typical required classes are imported from FastAPI, Pydantic, etc.
from lazyops.lazyrpc import *
from lazyops import get_logger

logger = get_logger('LazyTest')


# database models
class User:
    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        if not isinstance(other, User):
            return False
        return self.name == other.name


class Account:
    def __init__(self, account_id, owner, amount, currency):
        self.account_id = account_id
        self.owner = owner
        self.amount = amount
        self.currency = currency

    def owned_by(self, user: User):
        return self.owner == user

...

# JSON-RPC methods of this entrypoint
# this json-rpc method has one json-rpc-parameter 'account_id' and one header parameter 'user-auth-token'
@api_v1.method()
def get_balance(
    account: Account = Depends(get_account),
) -> Balance:
    return Balance(amount=account.amount, currency=account.currency,)


# this json-rpc method has two json-rpc-parameters 'account_id', 'amount' and one header parameter 'user-auth-token'
@api_v1.method(errors=[NotEnoughMoney])
def withdraw(
    account: Account = Depends(get_account),
    amount: int = Body(..., gt=0, example=10),
) -> Balance:
    if account.amount - amount < 0:
        raise NotEnoughMoney(data={'balance': get_balance(account)})
    account.amount -= amount
    return get_balance(account)


# JSON-RPC API
app = LazyJRPC()
app.bind_entrypoint(api_v1)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, port=5000, debug=True, access_log=False)

```