import asyncio
import logging
from azure.iot.device import (
    ProvisioningSession,
    MQTTConnectionDroppedError,
    MQTTConnectionFailedError,
)
import os
import ssl


id_scope = os.getenv("PROVISIONING_IDSCOPE")
registration_id = os.getenv("PROVISIONING_REGISTRATION_ID")

logging.basicConfig(level=logging.DEBUG)


async def main():
    try:
        ssl_context = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
        ssl_context.verify_mode = ssl.CERT_REQUIRED
        ssl_context.check_hostname = True
        ssl_context.load_default_certs()
        # These are all fake file names and password and to  be replaced as per scenario.
        ssl_context.load_cert_chain(
            certfile="device_cert4.pem",
            keyfile="device_key4.pem",
            password="devicepass",
        )

        async with ProvisioningSession(
            registration_id=registration_id,
            id_scope=id_scope,
            ssl_context=ssl_context,
        ) as session:
            print("Connected")
            result = await session.register(payload="optional registration payload")
            print("Finished provisioning")
            print(result)

    except MQTTConnectionDroppedError:
        # Connection has been lost.
        print("Dropped connection. Exiting")
    except MQTTConnectionFailedError:
        # Connection failed to be established.
        print("Could not connect. Exiting")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Exit application because user indicated they wish to exit.
        # This will have cancelled `main()` implicitly.
        print("User initiated exit. Exiting")
