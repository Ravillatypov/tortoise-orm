import warnings
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Optional, TypeVar, cast

from tortoise.exceptions import ParamsError

current_transaction_map: dict = {}

if TYPE_CHECKING:  # pragma: nocoverage
    from tortoise.backends.base.client import (
        BaseDBAsyncClient,
        BaseTransactionWrapper,
        TransactionContext,
    )

FuncType = Callable[..., Any]
F = TypeVar("F", bound=FuncType)


def _get_connection(connection_name: Optional[str]) -> "BaseDBAsyncClient":
    from tortoise import Tortoise

    if connection_name:
        connection = current_transaction_map[connection_name].get()
    elif len(Tortoise._connections) == 1:
        connection_name = list(Tortoise._connections.keys())[0]
        connection = current_transaction_map[connection_name].get()
    else:
        raise ParamsError(
            "You are running with multiple databases, so you should specify"
            f" connection_name: {list(Tortoise._connections.keys())}"
        )
    return connection


def in_transaction(connection_name: Optional[str] = None) -> "TransactionContext":
    """
    Transaction context manager.

    You can run your code inside ``async with in_transaction():`` statement to run it
    into one transaction. If error occurs transaction will rollback.

    :param connection_name: name of connection to run with, optional if you have only
                            one db connection
    """
    connection = _get_connection(connection_name)
    return connection._in_transaction()


def atomic(connection_name: Optional[str] = None) -> Callable[[F], F]:
    """
    Transaction decorator.

    You can wrap your function with this decorator to run it into one transaction.
    If error occurs transaction will rollback.

    :param connection_name: name of connection to run with, optional if you have only
                            one db connection
    """

    def wrapper(func: F) -> F:
        @wraps(func)
        async def wrapped(*args, **kwargs):
            connection = _get_connection(connection_name)
            async with connection._in_transaction():
                return await func(*args, **kwargs)

        return cast(F, wrapped)

    return wrapper


async def start_transaction(
    connection_name: Optional[str] = None,
) -> "BaseTransactionWrapper":  # pragma: nocoverage
    """
    Function to manually control your transaction.

    .. warning::
        **Deprecated, to be removed in v0.15**

        ``start_transaction`` leaks context.
        Please use ``@atomic()`` or ``async with in_transaction():`` instead.

    Returns transaction object with ``.rollback()`` and ``.commit()`` methods.
    All db calls in same coroutine context will run into transaction
    before ending transaction with above methods.

    :param connection_name: name of connection to run with, optional if you have only
                            one db connection
    """
    warnings.warn(
        "start_transaction leaks context,"
        " please use '@atomic()' or 'async with in_transaction():' instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    connection = _get_connection(connection_name)
    transaction = connection._in_transaction()
    await transaction.connection.start()
    return transaction.connection
