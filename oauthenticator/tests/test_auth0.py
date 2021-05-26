from pytest import fixture
from tornado import web
from unittest.mock import Mock

from ..auth0 import Auth0OAuthenticator
from ..auth0 import Auth0LogoutHandler
from .mocks import setup_oauth_mock
from .mocks import mock_handler

auth0_subdomain = "jupyterhub-test"


def user_model(email, nickname=None):
    """Return a user model"""
    return {
        'email': email,
        'nickname': nickname if nickname else email,
        'name': 'Hoban Washburn',
    }


@fixture
def auth0_client(client):
    setup_oauth_mock(
        client,
        host='%s.auth0.com' % auth0_subdomain,
        access_token_path='/oauth/token',
        user_path='/userinfo',
        token_request_style='json',
    )
    return client


async def test_auth0(auth0_client):
    authenticator = Auth0OAuthenticator(auth0_subdomain=auth0_subdomain)
    handler = auth0_client.handler_for_user(user_model('kaylee@serenity.now'))
    user_info = await authenticator.authenticate(handler)
    assert sorted(user_info) == ['auth_state', 'name']
    name = user_info['name']
    assert name == 'kaylee@serenity.now'
    auth_state = user_info['auth_state']
    assert 'access_token' in auth_state
    assert 'auth0_user' in auth_state


async def test_username_key(auth0_client):
    authenticator = Auth0OAuthenticator(auth0_subdomain=auth0_subdomain)
    authenticator.username_key = 'nickname'
    handler = auth0_client.handler_for_user(user_model('kaylee@serenity.now', 'kayle'))
    user_info = await authenticator.authenticate(handler)

    assert user_info['name'] == 'kayle'


async def test_custom_logout(monkeypatch):
    custom_logout_url = 'https://auth0-domain.org/logout'
    authenticator = Auth0OAuthenticator()
    logout_handler = mock_handler(Auth0LogoutHandler, authenticator=authenticator)
    monkeypatch.setattr(web.RequestHandler, 'redirect', Mock())

    logout_handler.clear_login_cookie = Mock()
    logout_handler.clear_cookie = Mock()
    logout_handler._jupyterhub_user = Mock()
    monkeypatch.setitem(logout_handler.settings, 'statsd', Mock())

    # Sanity check: Ensure the logout handler and url are set on the hub
    handlers = [handler for _, handler in authenticator.get_handlers(None)]
    assert any([h == Auth0LogoutHandler for h in handlers])
    assert authenticator.logout_url('http://myhost') == 'http://myhost/logout'

    # Check redirection to the custom logout url
    authenticator.logout_redirect_url = custom_logout_url
    await logout_handler.get()
    logout_handler.redirect.assert_called_with(custom_logout_url)
