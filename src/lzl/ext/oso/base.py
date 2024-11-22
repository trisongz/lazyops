from __future__ import annotations

"""
Oso Base Class
"""

import functools
import typing as t
from oso import Oso as BaseOso
from polar.exceptions import DuplicateClassAliasError, OsoError, PolarRuntimeError
from polar import Variable
from polar.partial import TypeConstraint
from lzl.pool import ThreadPool
from lzl.logging import logger
from lzl import load
from . import errors

if t.TYPE_CHECKING:
    from sqlalchemy.orm import DeclarativeBase, registry
    from sqlalchemy.orm import Session
    from sqlalchemy.ext.asyncio import AsyncSession
    import sqlalchemy.sql.expression

if load.TYPE_CHECKING:
    import sqlalchemy
    import sqlalchemy_oso.partial
else:
    sqlalchemy = load.LazyLoad("sqlalchemy")
    sqlalchemy_oso = load.LazyLoad("sqlalchemy_oso", install_missing=True)

_Action = str
_Request = t.TypeVar("_Request")
_Resource = t.TypeVar("_Resource")
_Actor = t.TypeVar("_Actor")
_ResourceCls = t.Type[_Resource]

class Oso(BaseOso):
    """The central object to manage application policy state, e.g.
    the policy data, and verify requests.

    >>> from lzl.ext.oso import Oso
    >>> Oso()
    <oso.oso.Oso object at 0x...>
    """

    _registered_: t.Dict[str, t.Dict[str, t.Union[_ResourceCls, t.Any]]] = {}

    def __init__(
        self,
        *,
        forbidden_error: t.Type[t.Union[errors.OsoException, BaseException]] = errors.ForbiddenError,
        not_found_error: t.Type[t.Union[errors.OsoException, BaseException]] = errors.NotFoundError,
        read_action: _Action = "read"
    ) -> None:
        """
        Create an Oso object.

        :param forbidden_error:
            Optionally override the error class that is raised when an action is
            unauthorized.
        :param not_found_error:
            Optionally override the error class that is raised by the
            ``authorize`` method when an action is unauthorized AND the actor
            does not have permission to ``"read"`` the resource (and thus should
            not know it exists).
        :param read_action:
            The action used by the ``authorize`` method to determine whether an
            authorization failure should raise a ``NotFoundError`` or a
            ``ForbiddenError``.
        """
        super().__init__(forbidden_error = forbidden_error, not_found_error = not_found_error, read_action = read_action)
        self._pooler = ThreadPool
        self.postinit_hook()
        self.post_init_register_predefined()
        
        if t.TYPE_CHECKING:
            self.forbidden_error: t.Type[errors.OsoException]
            self.not_found_error: t.Type[errors.OsoException]
    
    def postinit_hook(self):
        """
        Post Initialization Hook
        """
        pass

    def _get_object_name(self, obj: t.Union[_Actor, _Resource]) -> str:
        """
        Returns the name of the object
        """
        if hasattr(obj, "name"): return obj.name
        if hasattr(obj, "__tablename__"): return obj.__tablename__
        if hasattr(obj, "__name__"): return obj.__name__
        return obj.__class__.__name__ if hasattr(obj, "__class__") else str(obj)

    def _raise_not_found(
        self,
        actor: _Actor,
        action: _Action,
        resource: _Resource,
    ) -> None:
        """
        Raises a NotFoundError
        """
        raise self.not_found_error(
            resource = self._get_object_name(resource),
            action = action,
            actor = self._get_object_name(actor),
        )

    def _raise_forbidden(
        self,
        actor: _Actor,
        action: _Action,
        resource: _Resource,
    ) -> None:
        """
        Raises a ForbiddenError
        """
        return self.forbidden_error(
            resource = self._get_object_name(resource),
            action = action,
            actor = self._get_object_name(actor),
        )

    def authorize(
        self,
        actor: _Actor,
        action: _Action,
        resource: _Resource,
        *,
        check_read: bool = True
    ) -> None:
        """Ensure that ``actor`` is allowed to perform ``action`` on
        ``resource``.

        If the action is permitted with an ``allow`` rule in the policy, then
        this method returns ``None``. If the action is not permitted by the
        policy, this method will raise an error.

        The error raised by this method depends on whether the actor can perform
        the ``"read"`` action on the resource. If they cannot read the resource,
        then a ``NotFound`` error is raised. Otherwise, a ``ForbiddenError`` is
        raised.

        :param actor: The actor performing the request.
        :param action: The action the actor is attempting to perform.
        :param resource: The resource being accessed.

        :param check_read: If set to ``False``, a ``ForbiddenError`` is always
            thrown on authorization failures, regardless of whether the actor can
            read the resource. Default is ``True``.
        :type check_read: bool

        """
        if self.query_rule_once("allow", actor, action, resource):
            return
        if check_read and (
            action == self.read_action
            or not self.query_rule_once("allow", actor, self.read_action, resource)
        ):
            self._raise_not_found(actor, action, resource)
        self._raise_forbidden(actor, action, resource)
        

    def authorize_request(self, actor: _Actor, request: _Request) -> None:
        """Ensure that ``actor`` is allowed to send ``request`` to the server.

        Checks the ``allow_request`` rule of a policy.

        If the request is permitted with an ``allow_request`` rule in the
        policy, then this method returns ``None``. Otherwise, this method raises
        a ``ForbiddenError``.

        :param actor: The actor performing the request.
        :param request: An object representing the request that was sent by the
            actor.
        """
        if not self.query_rule_once("allow_request", actor, request):
            self._raise_forbidden(actor, "request", request)
    

    def authorize_field(
        self, actor: _Actor, action: _Action, resource: _Resource, field: str
    ) -> None:
        """Ensure that ``actor`` is allowed to perform ``action`` on a given
        ``resource``'s ``field``.

        If the action is permitted by an ``allow_field`` rule in the policy,
        then this method returns ``None``. If the action is not permitted by the
        policy, this method will raise a ``ForbiddenError``.

        :param actor: The actor performing the request.
        :param action: The action the actor is attempting to perform on the
            field.
        :param resource: The resource being accessed.
        :param field: The name of the field being accessed.
        """
        if not self.query_rule_once("allow_field", actor, action, resource, field):
            self._raise_forbidden(actor, action, resource)



    """
    Async Methods
    """
    
    async def ais_allowed(
        self, actor: _Actor, action: _Action, resource: _Resource
    ) -> bool:
        """Evaluate whether ``actor`` is allowed to perform ``action`` on ``resource``.

        Uses allow rules in the Polar policy to determine whether a request is
        permitted. ``actor`` and ``resource`` should be classes that have been
        registered with Polar using the :py:func:`register_class` function.

        :param actor: The actor performing the request.
        :param action: The action the actor is attempting to perform.
        :param resource: The resource being accessed.

        :return: ``True`` if the request is allowed, ``False`` otherwise.
        """
        return await self._pooler.arun(self.is_allowed, actor, action, resource)

    async def aget_allowed_actions(
        self, actor: _Actor, resource: _Resource, allow_wildcard: bool = False
    ) -> t.List[t.Any]:
        """Determine the actions ``actor`` is allowed to take on ``resource``.
        """
        return list(await self.aauthorized_actions(actor, resource, allow_wildcard = allow_wildcard))

    async def aauthorize(
        self,
        actor: _Actor,
        action: _Action,
        resource: _Resource,
        *,
        check_read: bool = True
    ) -> None:
        """Ensure that ``actor`` is allowed to perform ``action`` on
        ``resource``.

        If the action is permitted with an ``allow`` rule in the policy, then
        this method returns ``None``. If the action is not permitted by the
        policy, this method will raise an error.

        The error raised by this method depends on whether the actor can perform
        the ``"read"`` action on the resource. If they cannot read the resource,
        then a ``NotFound`` error is raised. Otherwise, a ``ForbiddenError`` is
        raised.

        :param actor: The actor performing the request.
        :param action: The action the actor is attempting to perform.
        :param resource: The resource being accessed.

        :param check_read: If set to ``False``, a ``ForbiddenError`` is always
            thrown on authorization failures, regardless of whether the actor can
            read the resource. Default is ``True``.
        :type check_read: bool

        """
        return await self._pooler.arun(self.authorize, actor, action, resource, check_read = check_read)

    async def aauthorize_request(self, actor: _Actor, request: _Request) -> None:
        """Ensure that ``actor`` is allowed to send ``request`` to the server.

        Checks the ``allow_request`` rule of a policy.

        If the request is permitted with an ``allow_request`` rule in the
        policy, then this method returns ``None``. Otherwise, this method raises
        a ``ForbiddenError``.

        :param actor: The actor performing the request.
        :param request: An object representing the request that was sent by the
            actor.
        """
        return await self._pooler.arun(self.authorize_request, actor, request)
    
    async def aauthorized_actions(
        self, actor: _Actor, resource: _Resource, allow_wildcard: bool = False
    ) -> t.Set[t.Any]:
        """Determine the actions ``actor`` is allowed to take on ``resource``.

        Collects all actions allowed by allow rules in the Polar policy for the
        given combination of actor and resource.

        Identical to ``Oso.get_allowed_actions``.

        :param actor: The actor for whom to collect allowed actions

        :param resource: The resource being accessed

        :param allow_wildcard: Flag to determine behavior if the policy
            contains an "unconstrained" action that could represent any action:
            ``allow(_actor, _action, _resource)``. If ``True``, the method will
            return ``["*"]``, if ``False`` (the default), the method will raise
            an exception.

        :type allow_wildcard: bool

        :return: A set containing all allowed actions.
        """
        return await self._pooler.arun(self.authorized_actions, actor, resource, allow_wildcard = allow_wildcard)

    async def aauthorize_field(
        self, actor: _Actor, action: _Action, resource: _Resource, field: str
    ) -> None:
        """Ensure that ``actor`` is allowed to perform ``action`` on a given
        ``resource``'s ``field``.

        If the action is permitted by an ``allow_field`` rule in the policy,
        then this method returns ``None``. If the action is not permitted by the
        policy, this method will raise a ``ForbiddenError``.

        :param actor: The actor performing the request.
        :param action: The action the actor is attempting to perform on the
            field.
        :param resource: The resource being accessed.
        :param field: The name of the field being accessed.
        """
        return await self._pooler.arun(self.authorize_field, actor, action, resource, field)
    

    async def aauthorized_fields(
        self,
        actor: _Actor,
        action: _Action,
        resource: _Resource,
        allow_wildcard: bool = False,
    ) -> t.Set[t.Any]:
        """Determine the fields of ``resource`` on which ``actor`` is allowed to
        perform  ``action``.

        Uses ``allow_field`` rules in the policy to find all allowed fields.

        :param actor: The actor for whom to collect allowed fields.
        :param action: The action being taken on the fields.
        :param resource: The resource being accessed.

        :param allow_wildcard: Flag to determine behavior if the policy \
            includes a wildcard field. E.g., a rule allowing any field: \
            ``allow_field(_actor, _action, _resource, _field)``. If ``True``, the \
            method will return ``["*"]``, if ``False``, the method will raise an \
            exception.

        :type allow_wildcard: bool

        :return: A set containing all allowed fields.
        """
        return await self._pooler.arun(self.authorized_fields, actor, action, resource, allow_wildcard = allow_wildcard)
    

    async def aauthorized_query(
        self, actor: _Actor, action: _Action, resource_cls: _ResourceCls
    ):
        """Create a query for resources of type ``resource_cls``
        that ``actor`` is allowed to perform ``action`` on. The
        query is built by using the ``build_query`` and ``combine_query``
        functions registered for the ``resource_cls``.

        :param actor: The actor for whom to collect allowed resources.
        :param action: The action that user wants to perform.
        :param resource_cls: The type of the resources.

        :return: A query to fetch the resources,
        """
        return await self._pooler.arun(self.authorized_query, actor, action, resource_cls)
    

    async def aauthorized_resources(
        self, actor: _Actor, action: _Action, resource_cls: _ResourceCls
    ) -> t.List[t.Any]:
        """Determine the resources of type ``resource_cls`` that ``actor``
        is allowed to perform ``action`` on.

        :param actor: The actor for whom to collect allowed resources.
        :param action: The action that user wants to perform.
        :param resource_cls: The type of the resources.

        :return: The requested resources.
        """
        return await self._pooler.arun(self.authorized_resources, actor, action, resource_cls)
    
    @staticmethod
    def get_sa_field_type(model: t.Type['DeclarativeBase'], field: str) -> t.Type['DeclarativeBase']:
        """
        Returns the type of the field
        """
        try:
            field = getattr(model, field)
        except AttributeError as e:
            raise PolarRuntimeError(f"Cannot get property {field} on {model}.") from e

        try:
            return field.entity.class_
        except AttributeError as e:
            raise PolarRuntimeError(
                f"Cannot determine type of {field} on {model}."
            ) from e

    @staticmethod
    def iterate_sa_model_classes(base_or_registry: t.Union[t.Type['DeclarativeBase'], 'registry']):
        """
        Return an iterator of model classes that descend from a declarative base
        (SQLAlchemy 1.3 or 1.4) or exist in a registry (SQLAlchemy 1.4).
        """
        try:  # 1.3 declarative base.
            # TODO (dhatch): Not sure this is legit b/c it uses an internal interface?
            models = base_or_registry._decl_class_registry.items()
            for name, model in models:
                if name != "_sa_module_registry":
                    if isinstance(
                        model, sqlalchemy.ext.declarative.clsregistry._MultipleClassMarker
                    ):
                        for model_ref in model.contents:
                            yield model_ref()
                    else:
                        yield model
        except AttributeError:
            try:  # 1.4 declarative base.
                mappers = base_or_registry.registry.mappers
            except AttributeError:  # 1.4 registry.
                mappers = base_or_registry.mappers
            yield from {mapper.class_ for mapper in mappers}

    @staticmethod
    def default_polar_model_name(model: type) -> str:
        """
        Return polar class name for SQLAlchemy model.
        """
        return model.__name__

    def register_sql_models(
        self, 
        *base_or_registry: t.Type['DeclarativeBase'],
    ):
        """
        Register all models in registry (SQLAlchemy 1.4) or declarative base
        class (1.3 and 1.4) ``base_or_registry`` with Oso as classes.
        """
        for registry in base_or_registry:
            for model in self.iterate_sa_model_classes(registry):
                if model in self.host.types:
                    # skip models that were manually registered
                    continue
                try:
                    self.register_class(model, name = self.default_polar_model_name(model))
                except DuplicateClassAliasError as e:
                    raise OsoError(
                        "Attempted to register two classes with the same name when automatically registering SQLAlchemy models\n"
                        "To fix this, try manually registering the new class. E.g.\n"
                        '  oso.register_class(MyModel, name="models::MyModel")\n'
                        "  register_models(oso, Base)\n"
                    ) from e

    def authorize_sa_model(
        self,
        actor: _Actor,
        action: _Action,
        session: t.Union['Session', 'AsyncSession'],  # sourcery skip: avoid-builtin-shadow
        model: t.Type['DeclarativeBase'],
    ):    # sourcery skip: avoid-builtin-shadow
        """Return SQLAlchemy expression that applies the policy to ``model``.

        Executing this query will return only authorized objects. If the request is
        not authorized, a query that always contains no result will be returned.

        :param oso: The oso class to use for evaluating the policy.
        :param actor: The actor to authorize.
        :param action: The action to authorize.

        :param session: The SQLAlchemy session.
        :param model: The model to authorize, must be a SQLAlchemy model or alias.
        """
        self.host.get_field = self.get_sa_field_type
        try:
            mapped_class = sqlalchemy.inspect(model, raiseerr=True).class_
        except AttributeError:
            raise TypeError(f"Expected a model; received: {model}")

        user_type = self.host.types.get(mapped_class)
        model_name = (
            user_type.name or self.default_polar_model_name(mapped_class)
            if user_type
            else self.default_polar_model_name(mapped_class)
        )
        resource = Variable("resource")
        constraint = TypeConstraint(resource, model_name)
        results = self.query_rule(
            "allow",
            actor,
            action,
            resource,
            bindings={resource: constraint},
            accept_expression=True,
        )
        combined_filter = None
        has_result = False
        for result in results:
            has_result = True
            resource_partial = result["bindings"]["resource"]
            if isinstance(resource_partial, model):
                def f(pk):
                    return getattr(model, pk) == getattr(resource_partial, pk)

                filters = [f(pk.name) for pk in sqlalchemy.inspect(model).primary_key]
                filter = functools.reduce(lambda a, b: a & b, filters)
            else:
                filter = sqlalchemy_oso.partial.partial_to_filter(
                    resource_partial, 
                    session, 
                    model, 
                    get_model = self.get_class
                )
            if combined_filter is None: combined_filter = filter
            else: combined_filter = combined_filter | filter
        return combined_filter if has_result else sqlalchemy.sql.expression.false()

    def register_classes(self, *classes: t.Type[_Actor]):
        """
        Registers the classes
        """
        for ct in classes:
            self.register_class(ct)

    def post_init_register_predefined(self, **kwargs):
        """
        Registers the predefined objects
        """
        if not self._registered_: return
        for name, config in self._registered_.items():
            new_cls = config.pop('cls')
            if isinstance(new_cls, str): new_cls = load.lazy_import(new_cls)
            new = {
                'name': name,
                **config,
            }
            self.register_class(new_cls, **new)

    @classmethod
    def _preregister_class(cls, model: _ResourceCls, name: t.Optional[str] = None, fields: t.Optional[t.List[str]] = None):
        """
        Preregisters a model
        """
        if name is None: name = cls.default_polar_model_name(model)
        cls._registered_[name] = {
            'cls': model,
            'fields': fields,
        }

    @classmethod
    def preregister_class(cls, name: t.Optional[str] = None, fields: t.Optional[t.List[str]] = None):
        """
        Preregisters the models
        """
        def wrapper(model: _ResourceCls):
            cls._preregister_class(model, name = name, fields = fields)
            return model
        return wrapper

    @classmethod
    def _preregister_lazy(cls, model_source: str, name: t.Optional[str] = None, fields: t.Optional[t.List[str]] = None):
        """
        Preregisters a model
        """
        if name is None: name = model_source.rsplit('.', 1)[-1]
        cls._registered_[name] = {
            'cls': model_source,
            'fields': fields,
        }

    @classmethod
    def preregister_lazy(cls, model_source: t.Union[str, t.List[str], t.Dict[str, t.Any]], name: t.Optional[str] = None, fields: t.Optional[t.List[str]] = None):
        """
        Lazily Preregisters the models
        """
        if isinstance(model_source, str):
            return cls._preregister_lazy(model_source, name = name, fields = fields)
        if isinstance(model_source, dict):
            for k, v in model_source.items():
                cls._preregister_lazy(v, name = k, fields = fields)
            return
        if isinstance(model_source, list):
            for v in model_source:
                cls._preregister_lazy(v, name = name, fields = fields)
            return
        raise ValueError(f'Invalid model_source: {model_source}')

    @classmethod
    def preregister(cls, model_or_source: t.Optional[t.Union[str, t.List[str], t.Dict[str, t.Any], _ResourceCls]] = None, name: t.Optional[str] = None, fields: t.Optional[t.List[str]] = None):
        """
        PreRegisters the models
        """
        if model_or_source is None: return cls.preregister_class(name = name, fields = fields)
        if isinstance(model_or_source, (str, list, dict)):
            return cls.preregister_lazy(model_or_source, name = name, fields = fields)
        return cls._preregister_class(model_or_source, name = name, fields = fields)
    
