from __future__ import unicode_literals

import mock

import pytest

import spotify

import mopidy_spotify.backend


@pytest.yield_fixture
def spotify_mock():
    patcher = mock.patch.object(
        mopidy_spotify.backend, 'spotify', spec=spotify)
    yield patcher.start()
    patcher.stop()


@pytest.fixture
def config():
    return {
        'spotify': {
            'username': 'alice',
            'password': 'password',
            'cache_dir': '/my/cache/dir',
            'settings_dir': '/my/settings/dir',
        }
    }


def get_backend(config):
    return mopidy_spotify.backend.SpotifyBackend(config=config, audio=None)


def test_uri_schemes(spotify_mock, config):
    backend = get_backend(config)

    assert 'spotify' in backend.uri_schemes


def test_init_creates_configured_session(spotify_mock, config):
    cache_location_mock = mock.PropertyMock()
    settings_location_mock = mock.PropertyMock()
    config_mock = spotify_mock.Config.return_value
    type(config_mock).cache_location = cache_location_mock
    type(config_mock).settings_location = settings_location_mock

    get_backend(config)

    spotify_mock.Config.assert_called_once_with()
    config_mock.load_application_key_file.assert_called_once_with(mock.ANY)
    cache_location_mock.assert_called_once_with('/my/cache/dir')
    settings_location_mock.assert_called_once_with('/my/settings/dir')
    spotify_mock.Session.assert_called_once_with(config_mock)


def test_init_adds_connection_state_changed_handler_to_session(
        spotify_mock, config):
    session = spotify_mock.Session.return_value

    get_backend(config)

    session.on.assert_called_once_with(
        spotify_mock.SessionEvent.CONNECTION_STATE_UPDATED, mock.ANY)


def test_on_start_starts_the_pyspotify_event_loop(spotify_mock, config):
    backend = get_backend(config)
    backend.on_start()

    spotify_mock.EventLoop.assert_called_once_with(backend._session)
    spotify_mock.EventLoop.return_value.start.assert_called_once_with()


def test_on_start_logs_in(spotify_mock, config):
    backend = get_backend(config)
    backend.on_start()

    spotify_mock.Session.return_value.login.assert_called_once_with(
        'alice', 'password')


def test_on_stop_logs_out_and_waits_for_logout_to_complete(
        spotify_mock, config, caplog):
    backend = get_backend(config)
    backend._logged_out = mock.Mock()

    backend.on_stop()

    assert 'Logging out of Spotify' in caplog.text()
    spotify_mock.Session.return_value.logout.assert_called_once_with()
    backend._logged_out.wait.assert_called_once_with()
    spotify_mock.EventLoop.return_value.stop.assert_called_once_with()


def test_on_connection_state_changed_when_logged_out(
        spotify_mock, config, caplog):
    session_mock = spotify_mock.Session.return_value
    session_mock.connection.state = spotify_mock.ConnectionState.LOGGED_OUT
    backend = get_backend(config)

    backend.on_connection_state_changed(session_mock)

    assert 'Logged out of Spotify' in caplog.text()
    assert not backend._logged_in.is_set()
    assert backend._logged_out.is_set()


def test_on_connection_state_changed_when_logged_in(
        spotify_mock, config, caplog):
    session_mock = spotify_mock.Session.return_value
    session_mock.connection.state = spotify_mock.ConnectionState.LOGGED_IN
    backend = get_backend(config)

    backend.on_connection_state_changed(session_mock)

    assert 'Logged in to Spotify in online mode' in caplog.text()
    assert backend._logged_in.is_set()
    assert not backend._logged_out.is_set()


def test_on_connection_state_changed_when_disconnected(
        spotify_mock, config, caplog):
    session_mock = spotify_mock.Session.return_value
    session_mock.connection.state = spotify_mock.ConnectionState.DISCONNECTED
    backend = get_backend(config)

    backend.on_connection_state_changed(session_mock)

    assert 'Disconnected from Spotify' in caplog.text()


def test_on_connection_state_changed_when_offline(
        spotify_mock, config, caplog):
    session_mock = spotify_mock.Session.return_value
    session_mock.connection.state = spotify_mock.ConnectionState.OFFLINE
    backend = get_backend(config)

    backend.on_connection_state_changed(session_mock)

    assert 'Logged in to Spotify in offline mode' in caplog.text()
    assert backend._logged_in.is_set()
    assert not backend._logged_out.is_set()