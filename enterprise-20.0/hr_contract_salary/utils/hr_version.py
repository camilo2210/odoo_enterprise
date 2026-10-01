import functools

from contextlib import contextmanager, AbstractContextManager
from typing import TypeVar

from odoo.http.requestlib import Request
from odoo.models import BaseModel

HR_VERSION_CTX_KEY = 'hr_version_ctx_savepoint'

T = TypeVar('T', bound='BaseModel | Request')


def requires_hr_version_context(key=HR_VERSION_CTX_KEY):
    """
    Decorator that asserts the decorated method is called within a savepoint context for hr.version
    """

    def decorator(func):
        if not callable(func):
            raise TypeError(f"Expected callable function/method, got {func!r} instead. Did you forget the ()?")

        is_private = func.__name__.startswith('_') or (hasattr(func, '_api_private') and func._api_private)
        if not is_private:
            # By definition, the method needs to be called within `hr_version_context`;
            # therefore, it's impossible for it to be externally exposed for API access.
            raise ValueError(
                f"Method '{func.__name__}' must be private to use @requires_hr_version_context() decorator."
            )

        @functools.wraps(func)
        def hr_version_context_wrapper(self, *args, **kwargs):
            if not self.env.context.get(key, False):
                ctx_manager_name = 'hr_version_context(...%s)' % (
                    f', key={key}'
                    if key != HR_VERSION_CTX_KEY
                    else ''
                )
                raise RuntimeError(
                    f"Method '{func.__name__}' must be called within a savepoint context. "
                    f"Use `{ctx_manager_name}` context manager before calling this method."
                )
            return func(self, *args, **kwargs)

        return hr_version_context_wrapper

    return decorator


@contextmanager
def _hr_version_ctx_records(records: BaseModel, **overrides):
    yield records.with_context(**overrides)


@contextmanager
def _hr_version_ctx_request(req: Request, **overrides):
    old_env = req.env
    req.update_context(**overrides)
    try:
        yield req
    finally:
        req.update_env(old_env.user, old_env.context, old_env.su)


@contextmanager
def hr_version_context(
    container: T,
    key: str = HR_VERSION_CTX_KEY,
    invalidate: bool = False,
    **overrides,
) -> AbstractContextManager[T]:
    """
    Context manager for hr.version operations that require isolated database operations.

    Creates a savepoint, yields with a prepared context for hr.version operations,
    then rolls back all changes made within the context.

    If `container` is a Request, the global `request` object is mutated, so the yielded result can be ignored at the caller site.
    """
    assert key not in overrides

    ctx_overrides = {
        key: True,
        'salary_simulation': True,
        'tracking_disable': True,  # rollbacked, hence no need to activate mail.thread features
        'is_simulation_offer': True,  # to prevent updating draft payslips
        **overrides,
    }

    container_ctx = None
    match container:
        case BaseModel():
            container_ctx = _hr_version_ctx_records
        case Request():
            container_ctx = _hr_version_ctx_request
        case _:
            raise TypeError(f"Expected BaseModel or Request, got {container!r} instead.")

    container.env.flush_all()
    with container_ctx(container, **ctx_overrides) as container:
        with container.env.cr.savepoint(flush=False) as sp:
            yield container

            container.env['hr.version']._track_clear()
            container.env.flush_all()
            sp.rollback()

    if invalidate:
        container.env['hr.version'].invalidate_model()
        container.env['hr.contract.salary.offer'].invalidate_model(['is_contract_amendment', 'contract_end_date'])
