from __future__ import annotations

from typing import Optional
from lzl.ext.fast.types.errors import FastAPIException, add_exception_handlers_to_app

class OAuth2Exception(FastAPIException):
    """
    OAuth2 Exception
    """
    module: Optional[str] = 'oauth2'
    concat_detail: Optional[bool] = True
    verbose: Optional[int] = None
    
    kind: Optional[str] = 'auth_error'
    status: Optional[int] = 400 # Default status code
    log_error: Optional[bool] = False # Always log the error message

class JWTDecodeError(OAuth2Exception):
    """
    JWT Decode Error
    """
    kind = 'jwt_decode_error'
    status = 401
    problem = 'The provided JWT Token could not be decoded'
    solution = 'Validate the JWT token and try again'

class JWTUnsupportedIssuerError(OAuth2Exception):
    """
    JWT Decode Error
    """
    kind = 'jwt_unsupported_issuer_error'
    status = 401
    problem = 'The issuer of the provided JWT Token is not supported'
    solution = 'Reauthenticate with a supported issuer and try again'

class InvalidTokenError(OAuth2Exception):
    """
    Invalid Token Error
    """
    kind = 'invalid_token_error'
    status = 401
    problem = 'The provided token is invalid'
    solution = 'Reauthenticate with a valid token and try again'

class InvalidAudienceError(OAuth2Exception):
    """
    Invalid Audience Error
    """
    kind = 'invalid_audience_error'
    status = 401
    problem = 'The provided audience is invalid'
    solution = 'Reauthenticate with a valid audience and try again'

class InvalidSignatureError(OAuth2Exception):
    """
    Invalid Signature Error
    """
    kind = 'invalid_signature_error'
    status = 401
    problem = 'The provided signature is invalid'
    solution = 'Reauthenticate with a valid signature and try again'

class InvalidRoleError(OAuth2Exception):
    """
    Invalid Role Error
    """
    kind = 'invalid_role_error'
    status = 401
    problem = 'The provided role is invalid'
    solution = 'Reauthenticate with a valid role and try again'

class UnauthorizedAccessError(OAuth2Exception):
    """
    Unauthorized Access Error
    """
    kind = 'unauthorized_access_error'
    status = 401
    problem = 'You are not authorized to access this resource'
    solution = 'Reauthenticate with a valid role and try again'

class InvalidScopeError(OAuth2Exception):
    """
    Invalid Scope Error
    """
    kind = 'invalid_scope_error'
    status = 401
    problem = 'The provided scope is invalid'
    solution = 'Reauthenticate with a valid scope and try again'

class MissingEmailFromJWTError(OAuth2Exception):
    """
    Missing Email From JWT Error
    """
    kind = 'missing_email_from_jwt_error'
    status = 401
    problem = 'The provided JWT Token does not contain an email'
    solution = 'Reauthenticate with a valid JWT Token and try again'

class UnauthorizedEmailAddressError(OAuth2Exception):
    """
    Unauthorized Email Address Error
    """
    kind = 'unauthorized_email_address_error'
    status = 401
    problem = 'The provided email address is not authorized'
    solution = 'Reauthenticate with a valid email address and try again'

class UnauthorizedEmailDomainError(OAuth2Exception):
    """
    Unauthorized Email Domain Error
    """
    kind = 'unauthorized_email_domain_error'
    status = 401
    problem = 'The provided email domain is not authorized'
    solution = 'Reauthenticate with a valid email domain and try again'

class MissingAuthorizationError(OAuth2Exception):
    """
    Missing Authorization Error
    """
    kind = 'missing_authorization_error'
    status = 401
    problem = 'No authorization provided'
    solution = 'Reauthenticate with a valid authorization and try again'

class InvalidApiKeyError(OAuth2Exception):
    """
    Invalid API Key Error
    """
    kind = 'invalid_api_key_error'
    status = 401
    problem = 'The provided api key is not valid'
    solution = 'Reauthenticate with a valid api key and try again'


class UnauthorizedApplicationError(OAuth2Exception):
    """
    Unauthorized Application Error
    """
    kind = 'unauthorized_application_error'
    status = 401
    problem = 'The provided user is not authorized to access this application'
    solution = 'Reauthenticate with a valid user and try again'

class UnauthorizedDomainError(OAuth2Exception):
    """
    Unauthorized Domain Error
    """
    kind = 'unauthorized_domain_error'
    status = 401
    problem = 'The provided user is not authorized to access this domain'
    solution = 'Reauthenticate with a valid user and try again'

class InvalidProviderError(OAuth2Exception):
    """
    Invalid Provider Error
    """
    kind = 'invalid_provider_error'
    status = 400
    problem = 'The provided auth provider ({provider}) is not valid or not supported'
    solution = 'Provide a valid auth provider and try again'

class InvalidAuthorizationError(OAuth2Exception):
    """
    Invalid Authorization Error
    """
    kind = 'invalid_authorization_error'
    status = 401
    problem = 'The provided authorization is not valid'
    solution = 'Reauthenticate with a valid authorization and try again'

class InvalidAuthzKeyError(OAuth2Exception):
    """
    Invalid Authz Key Error
    """
    kind = 'invalid_authz_key_error'
    status = 401
    problem = 'The provided authz key is not valid'
    solution = 'Reauthenticate with a valid authz key and try again'


class InvalidOfflineValidationError(OAuth2Exception):
    """
    Invalid Offline Validation Error
    """
    kind = 'invalid_offline_validation_error'
    status = 401
    problem = 'The provided offline validation SID is not valid'
    solution = 'Reauthenticate with a valid offline validation and try again'

class InvalidDomainError(OAuth2Exception):
    """
    Invalid Authz Redirect Domain Error
    """
    kind = 'invalid_domain_error'
    status = 401
    problem = 'The provided Key does not have access to this domain. Allowed Domains: {key_domains}'
    solution = 'Reauthenticate with a Key with access to this domain and try again'

class InvalidEnvironmentError(OAuth2Exception):
    """
    Invalid Environment Error
    """
    kind = 'invalid_environment_error'
    status = 401
    problem = 'The provided Key does not have access to this environment: {env}. Allowed Environments: {key_envs}'
    solution = 'Reauthenticate with a Key with access to this environment and try again'

class ExpiredTokenError(OAuth2Exception):
    """
    Expired Token Error
    """
    kind = 'expired_token_error'
    status = 401
    problem = 'The provided token has expired'
    solution = 'Reauthenticate with a valid token and try again'

class InvalidIdentityError(OAuth2Exception):
    """
    Invalid Identity Error
    """
    kind = 'invalid_identity_error'
    status = 401
    problem = 'The provided identity could not be found within the system'
    solution = 'Reauthenticate with a valid identity and try again'

class InvalidUserInfoError(OAuth2Exception):
    """
    Invalid User Info Error
    """
    kind = 'invalid_user_info_error'
    status = 401
    problem = 'The provided user info is invalid'
    solution = 'Reauthenticate with a valid user info and try again'

class InvalidAPIKeyError(OAuth2Exception):
    """
    Invalid API Key Error
    """
    kind = 'invalid_api_key_error'
    status = 401
    problem = 'The provided api key is not valid'
    solution = 'Reauthenticate with a valid api key and try again'

class NotAuthenticatedError(OAuth2Exception):
    """
    Not Authenticated Error
    """
    kind = 'not_authenticated_error'
    status = 401
    problem = 'You are not authenticated'
    solution = 'Authenticate with a valid user and try again'