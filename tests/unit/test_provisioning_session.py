import asyncio
import pytest
import ssl
import time
from dev_utils import custom_mock
from pytest_lazyfixture import lazy_fixture
from azure.iot.device.provisioning_session import ProvisioningSession
from azure.iot.device import config, constant
from azure.iot.device import exceptions as exc
from azure.iot.device import provisioning_mqtt_client as mqtt
from azure.iot.device import sastoken as st
from azure.iot.device import signing_mechanism as sm

FAKE_REGISTRATION_ID = "fake_registration_id"
FAKE_ID_SCOPE = "fake_idscope"
FAKE_HOSTNAME = "fake.hostname"
FAKE_URI = "fake/resource/location"
FAKE_SHARED_ACCESS_KEY = "Zm9vYmFy"
FAKE_SIGNATURE = "ajsc8nLKacIjGsYyB4iYDFCZaRMmmDrUuY5lncYDYPI="

# ~~~~~ Helpers ~~~~~~


def get_expected_uri():
    return "{id_scope}/registrations/{registration_id}".format(
        id_scope=FAKE_ID_SCOPE, registration_id=FAKE_REGISTRATION_ID
    )


# ~~~~~ Fixtures ~~~~~~

# Mock out the underlying client in order to not do network operations
@pytest.fixture(autouse=True)
def mock_mqtt_provisioning_client(mocker):
    mock_client = mocker.patch.object(
        mqtt, "ProvisioningMQTTClient", spec=mqtt.ProvisioningMQTTClient
    ).return_value
    # Use a HangingAsyncMock here so that the coroutine does not return until we want it to
    mock_client.wait_for_disconnect = custom_mock.HangingAsyncMock()
    return mock_client


@pytest.fixture
def sastoken_str():
    return "SharedAccessSignature sr={resource}&sig={signature}&se={expiry}".format(
        resource=FAKE_URI, signature=FAKE_SIGNATURE, expiry=str(int(time.time()) + 3600)
    )


@pytest.fixture
def custom_ssl_context():
    # NOTE: It doesn't matter how the SSLContext is configured for the tests that use this fixture,
    # so it isn't configured at all.
    return ssl.SSLContext()


@pytest.fixture(params=["Default SSLContext", "Custom SSLContext"])
def optional_ssl_context(request, custom_ssl_context):
    """Sometimes tests need to show something works with or without an SSLContext"""
    if request.param == "Custom SSLContext":
        return custom_ssl_context
    else:
        return None


@pytest.fixture
async def session(custom_ssl_context):
    """Use a symmetric key configuration and custom SSL auth for simplicity"""
    async with ProvisioningSession(
        registration_id=FAKE_REGISTRATION_ID,
        id_scope=FAKE_ID_SCOPE,
        shared_access_key=FAKE_SHARED_ACCESS_KEY,
        ssl_context=custom_ssl_context,
    ) as session:
        yield session


@pytest.fixture
def disconnected_session(custom_ssl_context):
    return ProvisioningSession(
        registration_id=FAKE_REGISTRATION_ID,
        id_scope=FAKE_ID_SCOPE,
        ssl_context=custom_ssl_context,
    )


# ~~~~~ Parametrizations ~~~~~
# Define parametrizations that will be used across multiple test suites, and that may eventually
# need to be changed everywhere, e.g. new auth scheme added.
# Note that some parametrizations are also defined within the scope of a single test suite if that
# is the only unit they are relevant to.


# Parameters for arguments to the __init__ or factory methods. Represent different types of
# authentication. Use this parametrization whenever possible on .create() tests.
# NOTE: Do NOT combine this with the SSL fixtures above. This parametrization contains
# ssl contexts where necessary
create_auth_params = [
    # Provide args in form 'shared_access_key, sastoken, ssl_context'
    pytest.param(
        FAKE_SHARED_ACCESS_KEY, None, None, id="Shared Access Key SAS Auth + Default SSLContext"
    ),
    pytest.param(
        FAKE_SHARED_ACCESS_KEY,
        None,
        lazy_fixture("custom_ssl_context"),
        id="Shared Access Key SAS Auth + Custom SSLContext",
    ),
    pytest.param(
        None,
        lazy_fixture("sastoken_str"),
        None,
        id="User-Provided SAS Token Auth + Default SSLContext",
    ),
    pytest.param(
        None,
        lazy_fixture("sastoken_str"),
        lazy_fixture("custom_ssl_context"),
        id="User-Provided SAS Token Auth + Custom SSLContext",
    ),
    pytest.param(None, None, lazy_fixture("custom_ssl_context"), id="Custom SSLContext Auth"),
]
# # Just the parameters where SAS auth is used
create_auth_params_sas = [param for param in create_auth_params if "SAS" in param.id]
# Just the parameters where a Shared Access Key auth is used
create_auth_params_sak = [param for param in create_auth_params if param.values[0] is not None]
# Just the parameters where a Shared Access Key auth is NOT used
create_auth_params_no_sak = [param for param in create_auth_params if param.values[0] is None]
# Just the parameters where user-provided SAS token auth is used
create_auth_params_user_token = [
    param for param in create_auth_params if param.values[1] is not None
]
# Just the parameters where user-provided SAS token auth is NOT used
create_auth_params_no_user_token = [
    param for param in create_auth_params if param.values[1] is None
]
# Just the parameters where a custom SSLContext is provided
create_auth_params_custom_ssl = [
    param for param in create_auth_params if param.values[2] is not None
]
# Just the parameters where a custom SSLContext is NOT provided
create_auth_params_default_ssl = [param for param in create_auth_params if param.values[2] is None]


# Covers all option kwargs shared across client factory methods
factory_kwargs = [
    # pytest.param("auto_reconnect", False, id="auto_reconnect"),
    pytest.param("keep_alive", 34, id="keep_alive"),
    pytest.param(
        "proxy_options", config.ProxyOptions("HTTP", "fake.address", 1080), id="proxy_options"
    ),
    pytest.param("websockets", True, id="websockets"),
]

sk_sm_create_exceptions = [
    pytest.param(ValueError(), id="ValueError"),
    pytest.param(lazy_fixture("arbitrary_exception"), id="Unexpected Exception"),
]

json_serializable_payload_params = [
    pytest.param("String payload", id="String Payload"),
    pytest.param(123, id="Integer Payload"),
    pytest.param(2.0, id="Float Payload"),
    pytest.param(True, id="Boolean Payload"),
    pytest.param({"dictionary": {"payload": "nested"}}, id="Dictionary Payload"),
    pytest.param([1, 2, 3], id="List Payload"),
    pytest.param((1, 2, 3), id="Tuple Payload"),
    pytest.param(None, id="No Payload"),
]


@pytest.mark.describe("ProvisioningSession -- Instantiation")
class TestProvisioningSessionInstantiation:
    @pytest.mark.it(
        "Instantiates and stores a SasTokenGenerator using the `shared_access_key`, if `shared_access_key` is provided"
    )
    @pytest.mark.parametrize("shared_access_key, sastoken, ssl_context", create_auth_params_sak)
    async def test_sak_auth(self, mocker, shared_access_key, sastoken, ssl_context):
        assert sastoken is None
        spy_sk_sm_cls = mocker.spy(sm, "SymmetricKeySigningMechanism")
        spy_st_generator_cls = mocker.spy(st, "SasTokenGenerator")
        expected_uri = get_expected_uri()

        session = ProvisioningSession(
            registration_id=FAKE_REGISTRATION_ID,
            id_scope=FAKE_ID_SCOPE,
            shared_access_key=shared_access_key,
            ssl_context=ssl_context,
        )

        # SymmetricKeySigningMechanism was created from the shared access key
        assert spy_sk_sm_cls.call_count == 1
        assert spy_sk_sm_cls.call_args == mocker.call(shared_access_key)
        # SasTokenGenerator was created from the SymmetricKeySigningMechanism
        assert spy_st_generator_cls.call_count == 1
        assert spy_st_generator_cls.call_args == mocker.call(
            signing_mechanism=spy_sk_sm_cls.spy_return, uri=expected_uri
        )
        # SasTokenGenerator was set on the Session
        assert session._sastoken_generator is spy_st_generator_cls.spy_return

    @pytest.mark.it(
        "Does not instantiate or store any SasTokenGenerator if no `shared_access_key` is provided"
    )
    @pytest.mark.parametrize("shared_access_key, sastoken, ssl_context", create_auth_params_no_sak)
    async def test_no_sak_auth(self, mocker, shared_access_key, sastoken, ssl_context):
        assert shared_access_key is None
        spy_st_generator_cls = mocker.spy(st, "SasTokenGenerator")

        session = ProvisioningSession(
            registration_id=FAKE_REGISTRATION_ID,
            id_scope=FAKE_ID_SCOPE,
            sastoken=sastoken,
            ssl_context=ssl_context,
        )

        assert spy_st_generator_cls.call_count == 0
        assert session._sastoken_generator is None

    @pytest.mark.it(
        "Instantiates and stores a SasToken from the `sastoken` string, if `sastoken` is provided"
    )
    @pytest.mark.parametrize(
        "shared_access_key, sastoken, ssl_context", create_auth_params_user_token
    )
    async def test_user_sastoken_auth(self, shared_access_key, sastoken, ssl_context):
        assert shared_access_key is None

        session = ProvisioningSession(
            registration_id=FAKE_REGISTRATION_ID,
            id_scope=FAKE_ID_SCOPE,
            sastoken=sastoken,
            ssl_context=ssl_context,
        )

        assert isinstance(session._user_sastoken, st.SasToken)
        assert str(session._user_sastoken) == sastoken

    @pytest.mark.it("Does not instantiate or store any SasToken if no `sastoken` is provided")
    @pytest.mark.parametrize(
        "shared_access_key, sastoken, ssl_context", create_auth_params_no_user_token
    )
    async def test_no_user_sastoken_auth(self, mocker, shared_access_key, sastoken, ssl_context):
        assert sastoken is None
        spy_st_cls = mocker.spy(st, "SasToken")

        session = ProvisioningSession(
            registration_id=FAKE_REGISTRATION_ID,
            id_scope=FAKE_ID_SCOPE,
            shared_access_key=shared_access_key,
            ssl_context=ssl_context,
        )

        assert spy_st_cls.call_count == 0
        assert session._user_sastoken is None

    # NOTE: It's not really valid to provide sastoken_ttl for anything other than
    # Shared Access Signature auth, but it isn't enforced because there's no harm in setting it
    # We test all possible cases here, not just valid ones
    @pytest.mark.it("Stores the provided `sastoken_ttl` value, if provided")
    @pytest.mark.parametrize("shared_access_key, sastoken, ssl_context", create_auth_params)
    async def test_sastoken_ttl_custom(self, shared_access_key, sastoken, ssl_context):
        custom_sastoken_ttl = 4700
        session = ProvisioningSession(
            registration_id=FAKE_REGISTRATION_ID,
            id_scope=FAKE_ID_SCOPE,
            shared_access_key=shared_access_key,
            ssl_context=ssl_context,
            sastoken=sastoken,
            sastoken_ttl=custom_sastoken_ttl,
        )
        assert session._sastoken_ttl == custom_sastoken_ttl

    # NOTE: It's not really valid to provide sastoken_ttl for anything other than
    # Shared Access Signature auth, but it isn't enforced because there's no harm in setting it
    # We test all possible cases here, not just valid ones
    @pytest.mark.it("Stores 3600 as the `sastoken_ttl` value, if no `sastoken_ttl` is provided")
    @pytest.mark.parametrize("shared_access_key, sastoken, ssl_context", create_auth_params)
    async def test_sastoken_ttl_default(self, shared_access_key, sastoken, ssl_context):
        session = ProvisioningSession(
            registration_id=FAKE_REGISTRATION_ID,
            id_scope=FAKE_ID_SCOPE,
            shared_access_key=shared_access_key,
            ssl_context=ssl_context,
            sastoken=sastoken,
        )
        assert session._sastoken_ttl == 3600

    @pytest.mark.it(
        "Instantiates and stores an ProvisioningMQTTClient, using a new ProvisioningClientConfig object"
    )
    @pytest.mark.parametrize("shared_access_key, sastoken, ssl_context", create_auth_params)
    async def test_mqtt_client(self, mocker, shared_access_key, sastoken, ssl_context):
        spy_config_cls = mocker.spy(config, "ProvisioningClientConfig")
        spy_mqtt_cls = mocker.spy(mqtt, "ProvisioningMQTTClient")
        assert spy_config_cls.call_count == 0
        assert spy_mqtt_cls.call_count == 0

        session = ProvisioningSession(
            registration_id=FAKE_REGISTRATION_ID,
            id_scope=FAKE_ID_SCOPE,
            shared_access_key=shared_access_key,
            ssl_context=ssl_context,
            sastoken=sastoken,
        )

        assert spy_config_cls.call_count == 1
        assert spy_mqtt_cls.call_count == 1
        assert spy_mqtt_cls.call_args == mocker.call(spy_config_cls.spy_return)
        assert session._mqtt_client is spy_mqtt_cls.spy_return

    @pytest.mark.it(
        "Sets the provided `provisioning_endpoint` as the `hostname` on the ProvisioningClientConfig used to create the ProvisioningMQTTClient, if `provisioning_endpoint` is provided"
    )
    @pytest.mark.parametrize("shared_access_key, sastoken, ssl_context", create_auth_params)
    async def test_custom_endpoint(self, mocker, shared_access_key, sastoken, ssl_context):
        spy_mqtt_cls = mocker.spy(mqtt, "ProvisioningMQTTClient")

        ProvisioningSession(
            provisioning_endpoint=FAKE_HOSTNAME,
            registration_id=FAKE_REGISTRATION_ID,
            id_scope=FAKE_ID_SCOPE,
            shared_access_key=shared_access_key,
            ssl_context=ssl_context,
            sastoken=sastoken,
        )

        cfg = spy_mqtt_cls.call_args[0][0]
        assert cfg.hostname == FAKE_HOSTNAME

    @pytest.mark.it(
        "Sets the Global Provisioning Endpoint as the `hostname` on the ProvisioningClientConfig used to create the ProvisioningMQTTClient, if no `provisioning_endpoint` is provided"
    )
    @pytest.mark.parametrize("shared_access_key, sastoken, ssl_context", create_auth_params)
    async def test_default_endpoint(self, mocker, shared_access_key, sastoken, ssl_context):
        spy_mqtt_cls = mocker.spy(mqtt, "ProvisioningMQTTClient")

        ProvisioningSession(
            registration_id=FAKE_REGISTRATION_ID,
            id_scope=FAKE_ID_SCOPE,
            shared_access_key=shared_access_key,
            ssl_context=ssl_context,
            sastoken=sastoken,
        )

        cfg = spy_mqtt_cls.call_args[0][0]
        assert cfg.hostname == constant.PROVISIONING_GLOBAL_ENDPOINT

    @pytest.mark.it(
        "Sets the provided `registration_id` and `id_scope` values on the ProvisioningClientConfig used to create the ProvisioningMQTTClient"
    )
    @pytest.mark.parametrize("shared_access_key, sastoken, ssl_context", create_auth_params)
    async def test_ids(self, mocker, shared_access_key, sastoken, ssl_context):
        spy_mqtt_cls = mocker.spy(mqtt, "ProvisioningMQTTClient")

        ProvisioningSession(
            registration_id=FAKE_REGISTRATION_ID,
            id_scope=FAKE_ID_SCOPE,
            shared_access_key=shared_access_key,
            ssl_context=ssl_context,
            sastoken=sastoken,
        )

        cfg = spy_mqtt_cls.call_args[0][0]
        assert cfg.registration_id == FAKE_REGISTRATION_ID
        assert cfg.id_scope == FAKE_ID_SCOPE

    @pytest.mark.it(
        "Sets the provided `ssl_context` on the ProvisioningClientConfig used to create the ProvisioningMQTTClient, if provided"
    )
    @pytest.mark.parametrize(
        "shared_access_key, sastoken, ssl_context", create_auth_params_custom_ssl
    )
    async def test_custom_ssl_context(self, mocker, shared_access_key, sastoken, ssl_context):
        spy_mqtt_cls = mocker.spy(mqtt, "ProvisioningMQTTClient")

        ProvisioningSession(
            registration_id=FAKE_REGISTRATION_ID,
            id_scope=FAKE_ID_SCOPE,
            shared_access_key=shared_access_key,
            ssl_context=ssl_context,
            sastoken=sastoken,
        )

        cfg = spy_mqtt_cls.call_args[0][0]
        assert cfg.ssl_context is ssl_context

    @pytest.mark.it(
        "Sets a default SSLContext on the ProvisioningClientConfig used to create the ProvisioningMQTTClient, if `ssl_context` is not provided"
    )
    @pytest.mark.parametrize(
        "shared_access_key, sastoken, ssl_context", create_auth_params_default_ssl
    )
    async def test_default_ssl_context(self, mocker, shared_access_key, sastoken, ssl_context):
        assert ssl_context is None
        spy_mqtt_cls = mocker.spy(mqtt, "ProvisioningMQTTClient")
        my_ssl_context = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_CLIENT)
        original_ssl_ctx_cls = ssl.SSLContext

        # NOTE: SSLContext is difficult to mock as an entire class, due to how it implements
        # instantiation. Essentially, if you mock the entire class, it will not be able to
        # instantiate due to an internal reference to the class type, which of course has now been
        # changed to MagicMock. To get around this, we mock the class with a side effect that can
        # check the arguments passed to the constructor, return a pre-existing SSLContext, and then
        # unset the mock to prevent future issues.
        def return_and_reset(*args, **kwargs):
            ssl.SSLContext = original_ssl_ctx_cls
            assert kwargs["protocol"] is ssl.PROTOCOL_TLS_CLIENT
            return my_ssl_context

        mocker.patch.object(ssl, "SSLContext", side_effect=return_and_reset)
        mocker.spy(my_ssl_context, "load_default_certs")

        ProvisioningSession(
            provisioning_endpoint=FAKE_HOSTNAME,
            registration_id=FAKE_REGISTRATION_ID,
            id_scope=FAKE_ID_SCOPE,
            shared_access_key=shared_access_key,
            sastoken=sastoken,
        )

        cfg = spy_mqtt_cls.call_args[0][0]
        ctx = cfg.ssl_context
        assert ctx is my_ssl_context
        # NOTE: ctx protocol is checked in the `return_and_reset` side effect above
        assert ctx.verify_mode == ssl.CERT_REQUIRED
        assert ctx.check_hostname is True
        assert ctx.load_default_certs.call_count == 1
        assert ctx.load_default_certs.call_args == mocker.call()
        assert ctx.minimum_version == ssl.TLSVersion.TLSv1_2

    @pytest.mark.it(
        "Sets `auto_reconnect` to False on the ProvisioningClientConfig used to create the ProvisioningMQTTClient"
    )
    @pytest.mark.parametrize("shared_access_key, sastoken, ssl_context", create_auth_params)
    async def test_auto_reconnect_cfg(self, mocker, shared_access_key, sastoken, ssl_context):
        spy_mqtt_cls = mocker.spy(mqtt, "ProvisioningMQTTClient")

        ProvisioningSession(
            provisioning_endpoint=FAKE_HOSTNAME,
            registration_id=FAKE_REGISTRATION_ID,
            id_scope=FAKE_ID_SCOPE,
            shared_access_key=shared_access_key,
            sastoken=sastoken,
            ssl_context=ssl_context,
        )

        cfg = spy_mqtt_cls.call_args[0][0]
        assert cfg.auto_reconnect is False

    @pytest.mark.it(
        "Sets any provided optional keyword arguments on the ProvisioningClientConfig used to create the ProvisioningMQTTClient"
    )
    @pytest.mark.parametrize("shared_access_key, sastoken, ssl_context", create_auth_params)
    @pytest.mark.parametrize("kwarg_name, kwarg_value", factory_kwargs)
    async def test_kwargs(
        self,
        mocker,
        shared_access_key,
        sastoken,
        ssl_context,
        kwarg_name,
        kwarg_value,
    ):
        spy_mqtt_cls = mocker.spy(mqtt, "ProvisioningMQTTClient")
        kwargs = {kwarg_name: kwarg_value}

        ProvisioningSession(
            provisioning_endpoint=FAKE_HOSTNAME,
            registration_id=FAKE_REGISTRATION_ID,
            id_scope=FAKE_ID_SCOPE,
            shared_access_key=shared_access_key,
            sastoken=sastoken,
            ssl_context=ssl_context,
            **kwargs
        )

        cfg = spy_mqtt_cls.call_args[0][0]
        assert getattr(cfg, kwarg_name) == kwarg_value

    @pytest.mark.it("Sets the `wait_for_disconnect_task` attribute to None")
    @pytest.mark.parametrize("shared_access_key, sastoken, ssl_context", create_auth_params)
    async def test_wait_for_disconnect_task(self, shared_access_key, sastoken, ssl_context):
        session = ProvisioningSession(
            provisioning_endpoint=FAKE_HOSTNAME,
            registration_id=FAKE_REGISTRATION_ID,
            id_scope=FAKE_ID_SCOPE,
            shared_access_key=shared_access_key,
            sastoken=sastoken,
            ssl_context=ssl_context,
        )
        assert session._wait_for_disconnect_task is None

    @pytest.mark.it(
        "Raises ValueError if neither `shared_access_key`, `sastoken` nor `ssl_context` are provided as parameters"
    )
    async def test_no_auth(self):
        with pytest.raises(ValueError):
            ProvisioningSession(
                registration_id=FAKE_REGISTRATION_ID,
                id_scope=FAKE_ID_SCOPE,
                provisioning_endpoint=FAKE_HOSTNAME,
            )

    @pytest.mark.it(
        "Raises ValueError if both `shared_access_key` and `sastoken` are provided as parameters"
    )
    async def test_conflicting_auth(self, sastoken_str, optional_ssl_context):
        with pytest.raises(ValueError):
            ProvisioningSession(
                registration_id=FAKE_REGISTRATION_ID,
                id_scope=FAKE_ID_SCOPE,
                provisioning_endpoint=FAKE_HOSTNAME,
                shared_access_key=FAKE_SHARED_ACCESS_KEY,
                sastoken=sastoken_str,
                ssl_context=optional_ssl_context,
            )

    @pytest.mark.it("Raises ValueError if the provided `sastoken` is already expired")
    async def test_expired_sastoken(self, optional_ssl_context):
        expired_sastoken_str = (
            "SharedAccessSignature sr={resource}&sig={signature}&se={expiry}".format(
                resource=FAKE_URI, signature=FAKE_SIGNATURE, expiry=str(int(time.time()) - 10)
            )
        )

        with pytest.raises(ValueError):
            ProvisioningSession(
                registration_id=FAKE_REGISTRATION_ID,
                id_scope=FAKE_ID_SCOPE,
                provisioning_endpoint=FAKE_HOSTNAME,
                shared_access_key=FAKE_SHARED_ACCESS_KEY,
                sastoken=expired_sastoken_str,
                ssl_context=optional_ssl_context,
            )

    @pytest.mark.it("Raises TypeError if an invalid keyword argument is provided")
    @pytest.mark.parametrize("shared_access_key, sastoken, ssl_context", create_auth_params)
    async def test_bad_kwarg(self, shared_access_key, sastoken, ssl_context):
        with pytest.raises(TypeError):
            ProvisioningSession(
                registration_id=FAKE_REGISTRATION_ID,
                id_scope=FAKE_ID_SCOPE,
                provisioning_endpoint=FAKE_HOSTNAME,
                shared_access_key=shared_access_key,
                sastoken=sastoken,
                ssl_context=ssl_context,
                invalid_argument="some value",
            )

    @pytest.mark.it(
        "Allows any exceptions raised when creating a SymmetricKeySigningMechanism to propagate"
    )
    @pytest.mark.parametrize("exception", sk_sm_create_exceptions)
    @pytest.mark.parametrize("shared_access_key, sastoken, ssl_context", create_auth_params_sak)
    async def test_sksm_raises(self, mocker, shared_access_key, sastoken, ssl_context, exception):
        mocker.patch.object(sm, "SymmetricKeySigningMechanism", side_effect=exception)
        assert sastoken is None

        with pytest.raises(type(exception)) as e_info:
            ProvisioningSession(
                registration_id=FAKE_REGISTRATION_ID,
                id_scope=FAKE_ID_SCOPE,
                provisioning_endpoint=FAKE_HOSTNAME,
                shared_access_key=shared_access_key,
                sastoken=sastoken,
                ssl_context=ssl_context,
            )
        assert e_info.value is exception


@pytest.mark.describe("ProvisioningSession -- Context Manager Usage")
class TestProvisioningSessionContextManager:
    @pytest.fixture
    def session(self, disconnected_session):
        return disconnected_session

    @pytest.mark.it(
        "Sets the user-provided SasToken on the ProvisioningMQTTClient upon entry into the context manager, if using user-provided SAS auth"
    )
    async def test_user_provided_sas(self, mocker, session, sastoken_str):
        session._user_sastoken = st.SasToken(sastoken_str)
        assert session._mqtt_client.set_sastoken.call_count == 0

        async with session as session:
            assert session._mqtt_client.set_sastoken.call_count == 1
            assert session._mqtt_client.set_sastoken.call_args == mocker.call(
                session._user_sastoken
            )

        assert session._mqtt_client.set_sastoken.call_count == 1

    @pytest.mark.it(
        "Generates a SasToken according to the configured TTL value, using the SasTokenGenerator, and sets it on the ProvisioningMQTTClient upon entry into the context manager, if using Shared Access Key SAS auth"
    )
    async def test_sak_generation_sas(self, mocker, session):
        session._sastoken_generator = mocker.MagicMock(spec=st.SasTokenGenerator)
        assert session._sastoken_generator.generate_sastoken.await_count == 0
        assert session._mqtt_client.set_sastoken.call_count == 0

        async with session as session:
            assert session._sastoken_generator.generate_sastoken.await_count == 1
            assert session._sastoken_generator.generate_sastoken.await_args == mocker.call(
                ttl=session._sastoken_ttl
            )
            assert session._mqtt_client.set_sastoken.call_count == 1
            assert session._mqtt_client.set_sastoken.call_args == mocker.call(
                session._sastoken_generator.generate_sastoken.return_value
            )

        assert session._sastoken_generator.generate_sastoken.call_count == 1
        assert session._mqtt_client.set_sastoken.call_count == 1

    @pytest.mark.it("Does not set any SasToken on the ProvisioningMQTTClient if not using SAS auth")
    async def test_no_sas(self, session):
        assert session._user_sastoken is None
        assert session._sastoken_generator is None
        assert session._mqtt_client.set_sastoken.call_count == 0

        async with session as session:
            assert session._mqtt_client.set_sastoken.call_count == 0

        assert session._mqtt_client.set_sastoken.call_count == 0

    @pytest.mark.it(
        "Starts the ProvisioningMQTTClient upon entry into the context manager, and stops it upon exit"
    )
    async def test_mqtt_client_start_stop(self, session):
        assert session._mqtt_client.start.await_count == 0
        assert session._mqtt_client.stop.await_count == 0

        async with session as session:
            assert session._mqtt_client.start.await_count == 1
            assert session._mqtt_client.stop.await_count == 0

        assert session._mqtt_client.start.await_count == 1
        assert session._mqtt_client.stop.await_count == 1

    @pytest.mark.it(
        "Stops the ProvisioningMQTTClient upon exit, even if an error was raised within the block inside the context manager"
    )
    async def test_mqtt_client_start_stop_with_failure(self, session, arbitrary_exception):
        assert session._mqtt_client.start.await_count == 0
        assert session._mqtt_client.stop.await_count == 0

        try:
            async with session as session:
                assert session._mqtt_client.start.await_count == 1
                assert session._mqtt_client.stop.await_count == 0
                raise arbitrary_exception
        except type(arbitrary_exception):
            pass

        assert session._mqtt_client.start.await_count == 1
        assert session._mqtt_client.stop.await_count == 1

    @pytest.mark.it(
        "Connect the ProvisioningMQTTClient upon entry into the context manager, and disconnect it upon exit"
    )
    async def test_mqtt_client_connection(self, session):
        assert session._mqtt_client.connect.await_count == 0
        assert session._mqtt_client.disconnect.await_count == 0

        async with session as session:
            assert session._mqtt_client.connect.await_count == 1
            assert session._mqtt_client.disconnect.await_count == 0

        assert session._mqtt_client.connect.await_count == 1
        assert session._mqtt_client.disconnect.await_count == 1

    @pytest.mark.it(
        "Disconnect the ProvisioningMQTTClient upon exit, even if an error was raised within the block inside the context manager"
    )
    async def test_mqtt_client_connection_with_failure(self, session, arbitrary_exception):
        assert session._mqtt_client.connect.await_count == 0
        assert session._mqtt_client.disconnect.await_count == 0

        try:
            async with session as session:
                assert session._mqtt_client.connect.await_count == 1
                assert session._mqtt_client.disconnect.await_count == 0
                raise arbitrary_exception
        except type(arbitrary_exception):
            pass

        assert session._mqtt_client.connect.await_count == 1
        assert session._mqtt_client.disconnect.await_count == 1

    @pytest.mark.it(
        "Creates a Task from the MQTTClient's .wait_for_disconnect() coroutine method and stores it as the `wait_for_disconnect_task` attribute upon entry into the context manager, and cancels and clears the Task upon exit"
    )
    async def test_wait_for_disconnect_task(self, mocker, session):
        assert session._wait_for_disconnect_task is None
        assert session._mqtt_client.wait_for_disconnect.call_count == 0

        async with session as session:
            # Task Created and Method called
            assert isinstance(session._wait_for_disconnect_task, asyncio.Task)
            assert not session._wait_for_disconnect_task.done()
            assert session._mqtt_client.wait_for_disconnect.call_count == 1
            assert session._mqtt_client.wait_for_disconnect.call_args == mocker.call()
            await asyncio.sleep(0.1)
            assert session._mqtt_client.wait_for_disconnect.is_hanging()
            # Returning method completes task (thus task corresponds to method)
            session._mqtt_client.wait_for_disconnect.stop_hanging()
            await asyncio.sleep(0.1)
            assert session._wait_for_disconnect_task.done()
            assert (
                session._wait_for_disconnect_task.result()
                is session._mqtt_client.wait_for_disconnect.return_value
            )
            # Replace the task with a mock so we can show it is cancelled/cleared on exit
            mock_task = mocker.MagicMock()
            session._wait_for_disconnect_task = mock_task
            assert mock_task.cancel.call_count == 0

        # Mocked task was cancelled and cleared
        assert mock_task.cancel.call_count == 1
        assert session._wait_for_disconnect_task is None

    @pytest.mark.it(
        "Cancels and clears the `wait_for_disconnect_task` Task, even if an error was raised within the block inside the context manager"
    )
    async def test_wait_for_disconnect_task_with_failure(self, session, arbitrary_exception):
        assert session._wait_for_disconnect_task is None

        try:
            async with session as session:
                task = session._wait_for_disconnect_task
                assert task is not None
                assert not task.done()
                raise arbitrary_exception
        except type(arbitrary_exception):
            pass

        await asyncio.sleep(0.1)
        assert session._wait_for_disconnect_task is None
        assert task.done()
        assert task.cancelled()

    @pytest.mark.it(
        "Allows any errors raised within the block inside the context manager to propagate"
    )
    @pytest.mark.parametrize(
        "exception",
        [
            pytest.param(lazy_fixture("arbitrary_exception"), id="Unexpected Exception"),
            # NOTE: it is important to test the CancelledError since it is a regular Exception in 3.7,
            # but a BaseException from 3.8+
            pytest.param(asyncio.CancelledError(), id="CancelledError"),
        ],
    )
    async def test_error_propagation(self, session, exception):
        with pytest.raises(type(exception)) as e_info:
            async with session as session:
                raise exception
        assert e_info.value is exception

    # NOTE: This shouldn't happen, but we test it anyway
    @pytest.mark.it(
        "Allows any errors raised while starting the ProvisioningMQTTClient during context manager entry to propagate"
    )
    async def test_enter_mqtt_client_start_raises(self, session, arbitrary_exception):
        session._mqtt_client.start.side_effect = arbitrary_exception

        with pytest.raises(type(arbitrary_exception)) as e_info:
            async with session as session:
                pass
        assert e_info.value is arbitrary_exception

    # NOTE: This shouldn't happen, but we test it anyway
    @pytest.mark.it(
        "Stops the ProvisioningMQTTClient that was previously started, and does not create the `wait_for_disconnect_task`, if an error is raised while starting the ProvisioningMQTTClient during context manager entry"
    )
    async def test_enter_mqtt_client_start_raises_cleanup(
        self, mocker, session, arbitrary_exception
    ):
        session._mqtt_client.start.side_effect = arbitrary_exception
        assert session._mqtt_client.stop.await_count == 0
        assert session._wait_for_disconnect_task is None
        spy_create_task = mocker.spy(asyncio, "create_task")

        with pytest.raises(type(arbitrary_exception)):
            async with session as session:
                pass

        assert session._mqtt_client.stop.await_count == 1
        assert session._wait_for_disconnect_task is None
        assert spy_create_task.call_count == 0

    @pytest.mark.it(
        "Allows any errors raised while connecting with the ProvisioningMQTTClient during context manager entry to propagate"
    )
    @pytest.mark.parametrize(
        "exception",
        [
            pytest.param(exc.MQTTConnectionFailedError(), id="MQTTConnectionFailedError"),
            pytest.param(lazy_fixture("arbitrary_exception"), id="Unexpected Exception"),
        ],
    )
    async def test_enter_mqtt_client_connect_raises(self, session, exception):
        session._mqtt_client.connect.side_effect = exception

        with pytest.raises(type(exception)) as e_info:
            async with session as session:
                pass
        assert e_info.value is exception

    @pytest.mark.it(
        "Stops the ProvisioningMQTTClient that was previously started, and does not create the `wait_for_disconnect_task`, if an error is raised while connecting during context manager entry"
    )
    @pytest.mark.parametrize(
        "exception",
        [
            pytest.param(exc.MQTTConnectionFailedError(), id="MQTTConnectionFailedError"),
            pytest.param(lazy_fixture("arbitrary_exception"), id="Unexpected Exception"),
        ],
    )
    async def test_enter_mqtt_client_connect_raises_cleanup(self, mocker, session, exception):
        session._mqtt_client.connect.side_effect = exception
        assert session._mqtt_client.stop.await_count == 0
        assert session._wait_for_disconnect_task is None
        spy_create_task = mocker.spy(asyncio, "create_task")

        with pytest.raises(type(exception)):
            async with session as session:
                pass

        assert session._mqtt_client.stop.await_count == 1
        assert session._wait_for_disconnect_task is None
        assert spy_create_task.call_count == 0

    # NOTE: This shouldn't happen, but we test it anyway
    @pytest.mark.it(
        "Allows any errors raised while disconnecting the ProvisioningMQTTClient during context manager exit to propagate"
    )
    async def test_exit_disconnect_raises(self, session, arbitrary_exception):
        session._mqtt_client.disconnect.side_effect = arbitrary_exception

        with pytest.raises(type(arbitrary_exception)) as e_info:
            async with session as session:
                pass
        assert e_info.value is arbitrary_exception

    # NOTE: This shouldn't happen, but we test it anyway
    @pytest.mark.it(
        "Stops the ProvisioningMQTTClient and cancels and clears the `wait_for_disconnect_task`, even if an error was raised while disconnecting the ProvisioningMQTTClient during context manager exit"
    )
    async def test_exit_disconnect_raises_cleanup(self, session, arbitrary_exception):
        session._mqtt_client.disconnect.side_effect = arbitrary_exception
        assert session._mqtt_client.stop.await_count == 0
        assert session._wait_for_disconnect_task is None

        with pytest.raises(type(arbitrary_exception)):
            async with session as session:
                conn_drop_task = session._wait_for_disconnect_task
                assert not conn_drop_task.done()

        assert session._mqtt_client.stop.await_count == 1
        await asyncio.sleep(0.1)
        assert session._wait_for_disconnect_task is None
        assert conn_drop_task.cancelled()

    # NOTE: This shouldn't happen, but we test it anyway
    @pytest.mark.it(
        "Allows any errors raised while stopping the ProvisioningMQTTClient during context manager exit to propagate"
    )
    async def test_exit_mqtt_client_stop_raises(self, session, arbitrary_exception):
        session._mqtt_client.stop.side_effect = arbitrary_exception

        with pytest.raises(type(arbitrary_exception)) as e_info:
            async with session as session:
                pass
        assert e_info.value is arbitrary_exception

    # NOTE: This shouldn't happen, but we test it anyway
    @pytest.mark.it(
        "Disconnects the ProvisioningMQTTClient and cancels and clears the `wait_for_disconnect_task`, even if an error was raised while stopping the ProvisioningMQTTClient during context manager exit"
    )
    async def test_exit_mqtt_client_stop_raises_cleanup(self, session, arbitrary_exception):
        session._mqtt_client.stop.side_effect = arbitrary_exception
        assert session._mqtt_client.disconnect.await_count == 0
        assert session._wait_for_disconnect_task is None

        with pytest.raises(type(arbitrary_exception)):
            async with session as session:
                conn_drop_task = session._wait_for_disconnect_task
                assert not conn_drop_task.done()

        assert session._mqtt_client.disconnect.await_count == 1
        await asyncio.sleep(0.1)
        assert session._wait_for_disconnect_task is None
        assert conn_drop_task.cancelled()

    # TODO: consider adding detailed cancellation tests
    # Not sure how cancellation would work in a context manager situation, needs more investigation


@pytest.mark.describe("ProvisioningSession - .register()")
class TestProvisioningSessionRegister:
    @pytest.mark.it(
        "Invokes .send_register() on the ProvisioningMQTTClient, passing the provided `payload`, if provided"
    )
    @pytest.mark.parametrize("payload", json_serializable_payload_params)
    async def test_invoke_with_payload(self, mocker, session, payload):
        assert session._mqtt_client.send_register.await_count == 0

        await session.register(payload)

        assert session._mqtt_client.send_register.await_count == 1
        assert session._mqtt_client.send_register.await_args == mocker.call(payload)

    @pytest.mark.it(
        "Invokes .send_register() on the ProvisioningMQTTClient, passing None, if no `payload` is provided"
    )
    async def test_invoke_no_payload(self, mocker, session):
        assert session._mqtt_client.send_register.await_count == 0

        await session.register()

        assert session._mqtt_client.send_register.await_count == 1
        assert session._mqtt_client.send_register.await_args == mocker.call(None)

    @pytest.mark.it("Allows any exceptions raised by the ProvisioningMQTTClient to propagate")
    @pytest.mark.parametrize(
        "exception",
        [
            pytest.param(exc.ProvisioningServiceError(), id="ProvisioningServiceError"),
            pytest.param(exc.MQTTError(5), id="MQTTError"),
            pytest.param(asyncio.CancelledError(), id="CancelledError"),
            pytest.param(lazy_fixture("arbitrary_exception"), id="Unexpected Error"),
        ],
    )
    @pytest.mark.parametrize("payload", json_serializable_payload_params)
    async def test_mqtt_client_raises(self, session, exception, payload):
        session._mqtt_client.send_register.side_effect = exception

        with pytest.raises(type(exception)) as e_info:
            await session.register(payload)
        # CancelledError doesn't propagate in some versions of Python
        # TODO: determine which versions exactly
        if not isinstance(exception, asyncio.CancelledError):
            assert e_info.value is exception

    @pytest.mark.it(
        "Raises SessionError without invoking .register() on the ProvisioningMQTTClient if it is not connected"
    )
    @pytest.mark.parametrize("payload", json_serializable_payload_params)
    async def test_not_connected(self, mocker, session, payload):
        conn_property_mock = mocker.PropertyMock(return_value=False)
        type(session._mqtt_client).connected = conn_property_mock

        with pytest.raises(exc.SessionError):
            await session.register(payload)
        assert session._mqtt_client.send_register.call_count == 0

    @pytest.mark.it(
        "Raises CancelledError if an expected disconnect occurs in the ProvisioningMQTTClient while waiting for the operation to complete"
    )
    @pytest.mark.parametrize("payload", json_serializable_payload_params)
    async def test_expected_disconnect_during_send(self, session, payload):
        session._mqtt_client.send_register = custom_mock.HangingAsyncMock()

        t = asyncio.create_task(session.register(payload))

        # Hanging, waiting for send to finish
        await session._mqtt_client.send_register.wait_for_hang()
        assert not t.done()

        # No disconnect yet
        assert not session._wait_for_disconnect_task.done()
        assert session._mqtt_client.wait_for_disconnect.call_count == 1
        assert session._mqtt_client.wait_for_disconnect.is_hanging()

        # Simulate expected disconnect
        session._mqtt_client.wait_for_disconnect.return_value = None
        session._mqtt_client.wait_for_disconnect.stop_hanging()

        with pytest.raises(asyncio.CancelledError):
            await t

    @pytest.mark.it(
        "Raises the MQTTConnectionDroppedError that caused the unexpected disconnect, if an unexpected disconnect occurs in the "
        "ProvisioningMQTTClient while waiting for the operation to complete"
    )
    @pytest.mark.parametrize("payload", json_serializable_payload_params)
    async def test_unexpected_disconnect_during_send(self, session, payload):
        session._mqtt_client.send_register = custom_mock.HangingAsyncMock()

        t = asyncio.create_task(session.register(payload))

        # Hanging, waiting for send to finish
        await session._mqtt_client.send_register.wait_for_hang()
        assert not t.done()

        # No unexpected disconnect yet
        assert not session._wait_for_disconnect_task.done()
        assert session._mqtt_client.wait_for_disconnect.call_count == 1
        assert session._mqtt_client.wait_for_disconnect.is_hanging()

        # Simulate unexpected disconnect
        cause = exc.MQTTConnectionDroppedError(rc=7)
        session._mqtt_client.wait_for_disconnect.return_value = cause
        session._mqtt_client.wait_for_disconnect.stop_hanging()

        with pytest.raises(exc.MQTTConnectionDroppedError) as e_info:
            await t
        assert e_info.value is cause

    @pytest.mark.it(
        "Can be cancelled while waiting for the ProvisioningMQTTClient operation to complete"
    )
    @pytest.mark.parametrize("payload", json_serializable_payload_params)
    async def test_cancel_during_send(self, session, payload):
        session._mqtt_client.send_register = custom_mock.HangingAsyncMock()

        t = asyncio.create_task(session.register(payload))

        # Hanging, waiting for send to finish
        await session._mqtt_client.send_register.wait_for_hang()
        assert not t.done()

        # Cancel
        t.cancel()
        with pytest.raises(asyncio.CancelledError):
            await t
