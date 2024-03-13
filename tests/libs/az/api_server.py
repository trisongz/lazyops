"""
Below Demonstrates a minimal app that can be used to test the authzero framework

NOTE:

If the application does not require the `login` and `callback` endpoints, then the following can be removed:
    - `app_auth.authorize_auth0()` from the `startup` event
    - `app.get('/login')` endpoint
    - `app.get('/auth/callback')` endpoint
    - `app.get('/logout')` endpoint

    Additionally, `app_client_id` is not required if the above endpoints are not required.
    You can simply just use the annotated `CurrentUser` dependency to get the user. 
"""

import time
import contextlib
from fastapi import FastAPI, Request
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import JSONResponse, RedirectResponse, PlainTextResponse
from fastapi.background import BackgroundTasks
from lazyops.libs.authzero import az_settings, AuthZeroOAuthClient, OptionalUser, ValidUser, CurrentUser, require_auth_role
from lazyops.utils.logs import logger
from typing import Annotated, Optional


# Mock Settings
app_settings = dict(
    app_name = "test app",
    app_description = "test app description",
    app_scopes = ['openid', 'profile', 'email'], # these are the scopes that the auth will validate against.
)
auth_settings = dict(
    client_id = '...', # this should be a valid `machine-to-machine` client id
    client_secret = '...', # this should be a valid `machine-to-machine` client secret
    audience = 'https://...', # Ensure this is your valid auth0 audience
    domain = 'domain.us.auth0.com', # Ensure this is your valid auth0 domain

    user_data_expiration = 60, # Allow for testing of expiration of user data and session
    user_session_expiration = 60, # This will expire the session after 60 seconds

    app_name = app_settings['app_name'],
    app_ingress = "http://localhost:8085",
    app_env = "local",
    app_scopes = app_settings['app_scopes'],

    # This should be a valid `single-page-application` client-id
    # however, this is not required for the auth to work, only if
    # you wish to enable the `login` and `callback` endpoints
    app_client_id = "....", 
    allowed_api_keys = ['abc123'],

    api_key_access_key = ('abc123' * 10)[:16], # Use a valid api key access key here to enable `api_key` authentication
    api_key_secret_key = ('321bca' * 10)[:16], # Use a valid api key secret key here to enable `api_key` authentication
)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context Manager for the lifespan of the app
    """
    logger.info("Starting up App")

    # This authorizes the app with Auth0
    # This step is optional but if its not done manually, 
    # then it could lead to authorization errors later on

    # this is not required for pure authentication
    # only if you wish to enable the `login` and `callback` endpoints
    try:
        await app_auth.authorize_app_in_authzero()
    except Exception as e:
        logger.trace("Error authorizing app", e)
    yield
    

app: FastAPI = FastAPI(
    app_name = app_settings['app_name'],
    description = app_settings['app_description'],
    lifespan = lifespan,
)

az_settings.configure(**auth_settings)

app_auth = AuthZeroOAuthClient(app)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
app_auth.mount_oauth_components()


@app.get('/')
async def mock_index(
    current_user: OptionalUser,
):
    """
    Returns the index if the user is logged in. Otherwise, redirects to the login page.
    """
    if current_user is None:
        return RedirectResponse(app.url_path_for('login'))
    logger.info(f'User {current_user.user_id} logged in')
    return JSONResponse({'user': current_user.user_id, 'x-api-key': current_user.api_key, 'user': current_user.dict()})

@app.get('/healthz', include_in_schema = False)
async def get_api_health(request: Request):
    """
    Returns the health of the server
    """
    return PlainTextResponse(content = 'healthy')

@app.get('/test')
async def test_api(
    request: Request, 
    current_user: ValidUser):
    """
    Test API
    """
    return JSONResponse(
        {
            'user': current_user.user_id, 
            'session_expiration': current_user.session.expiration_ts - time.time(),
            'user_data_expiration': current_user.user_data.expiration_ts - time.time(),
            'user_roles': current_user.user_roles,
            'role': current_user.role,
        }
    )


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='localhost', port=8085)