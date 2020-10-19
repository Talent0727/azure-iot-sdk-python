# coding=utf-8
# --------------------------------------------------------------------------
# Code generated by Microsoft (R) AutoRest Code Generator.
# Changes may cause incorrect behavior and will be lost if the code is
# regenerated.
# --------------------------------------------------------------------------

from msrest.pipeline import ClientRawResponse
from msrest.exceptions import HttpOperationError

from .. import models


class CloudToDeviceMessagesOperations(object):
    """CloudToDeviceMessagesOperations operations.

    :param client: Client for service requests.
    :param config: Configuration of service client.
    :param serializer: An object model serializer.
    :param deserializer: An object model deserializer.
    :ivar api_version: The API version to use for the request. Constant value: "2020-05-31-preview".
    """

    models = models

    def __init__(self, client, config, serializer, deserializer):

        self._client = client
        self._serialize = serializer
        self._deserialize = deserializer

        self.config = config
        self.api_version = "2020-05-31-preview"

    def purge_cloud_to_device_message_queue(
        self, id, custom_headers=None, raw=False, **operation_config
    ):
        """Deletes all the pending commands for a device in the IoT Hub.

        :param id: The unique identifier of the device.
        :type id: str
        :param dict custom_headers: headers that will be added to the request
        :param bool raw: returns the direct response alongside the
         deserialized response
        :param operation_config: :ref:`Operation configuration
         overrides<msrest:optionsforoperations>`.
        :return: PurgeMessageQueueResult or ClientRawResponse if raw=true
        :rtype: ~protocol.models.PurgeMessageQueueResult or
         ~msrest.pipeline.ClientRawResponse
        :raises:
         :class:`HttpOperationError<msrest.exceptions.HttpOperationError>`
        """
        # Construct URL
        url = self.purge_cloud_to_device_message_queue.metadata["url"]
        path_format_arguments = {"id": self._serialize.url("id", id, "str")}
        url = self._client.format_url(url, **path_format_arguments)

        # Construct parameters
        query_parameters = {}
        query_parameters["api-version"] = self._serialize.query(
            "self.api_version", self.api_version, "str"
        )

        # Construct headers
        header_parameters = {}
        header_parameters["Accept"] = "application/json"
        if custom_headers:
            header_parameters.update(custom_headers)

        # Construct and send request
        request = self._client.delete(url, query_parameters, header_parameters)
        response = self._client.send(request, stream=False, **operation_config)

        if response.status_code not in [200]:
            raise HttpOperationError(self._deserialize, response)

        deserialized = None

        if response.status_code == 200:
            deserialized = self._deserialize("PurgeMessageQueueResult", response)

        if raw:
            client_raw_response = ClientRawResponse(deserialized, response)
            return client_raw_response

        return deserialized

    purge_cloud_to_device_message_queue.metadata = {"url": "/devices/{id}/commands"}

    def receive_feedback_notification(self, custom_headers=None, raw=False, **operation_config):
        """Gets the feedback for cloud-to-device messages. See
        https://docs.microsoft.com/azure/iot-hub/iot-hub-devguide-messaging for
        more information. This capability is only available in the standard
        tier IoT Hub. For more information, see [Choose the right IoT Hub
        tier](https://aka.ms/scaleyouriotsolution).

        :param dict custom_headers: headers that will be added to the request
        :param bool raw: returns the direct response alongside the
         deserialized response
        :param operation_config: :ref:`Operation configuration
         overrides<msrest:optionsforoperations>`.
        :return: None or ClientRawResponse if raw=true
        :rtype: None or ~msrest.pipeline.ClientRawResponse
        :raises:
         :class:`HttpOperationError<msrest.exceptions.HttpOperationError>`
        """
        # Construct URL
        url = self.receive_feedback_notification.metadata["url"]

        # Construct parameters
        query_parameters = {}
        query_parameters["api-version"] = self._serialize.query(
            "self.api_version", self.api_version, "str"
        )

        # Construct headers
        header_parameters = {}
        if custom_headers:
            header_parameters.update(custom_headers)

        # Construct and send request
        request = self._client.get(url, query_parameters, header_parameters)
        response = self._client.send(request, stream=False, **operation_config)

        if response.status_code not in [200, 204]:
            raise HttpOperationError(self._deserialize, response)

        if raw:
            client_raw_response = ClientRawResponse(None, response)
            return client_raw_response

    receive_feedback_notification.metadata = {"url": "/messages/serviceBound/feedback"}

    def complete_feedback_notification(
        self, lock_token, custom_headers=None, raw=False, **operation_config
    ):
        """Completes the cloud-to-device feedback message. A completed message is
        deleted from the feedback queue of the service. See
        https://docs.microsoft.com/azure/iot-hub/iot-hub-devguide-messaging for
        more information.

        :param lock_token: The lock token obtained when the cloud-to-device
         message is received. This is used to resolve race conditions when
         completing a feedback message.
        :type lock_token: str
        :param dict custom_headers: headers that will be added to the request
        :param bool raw: returns the direct response alongside the
         deserialized response
        :param operation_config: :ref:`Operation configuration
         overrides<msrest:optionsforoperations>`.
        :return: None or ClientRawResponse if raw=true
        :rtype: None or ~msrest.pipeline.ClientRawResponse
        :raises:
         :class:`HttpOperationError<msrest.exceptions.HttpOperationError>`
        """
        # Construct URL
        url = self.complete_feedback_notification.metadata["url"]
        path_format_arguments = {"lockToken": self._serialize.url("lock_token", lock_token, "str")}
        url = self._client.format_url(url, **path_format_arguments)

        # Construct parameters
        query_parameters = {}
        query_parameters["api-version"] = self._serialize.query(
            "self.api_version", self.api_version, "str"
        )

        # Construct headers
        header_parameters = {}
        if custom_headers:
            header_parameters.update(custom_headers)

        # Construct and send request
        request = self._client.delete(url, query_parameters, header_parameters)
        response = self._client.send(request, stream=False, **operation_config)

        if response.status_code not in [204]:
            raise HttpOperationError(self._deserialize, response)

        if raw:
            client_raw_response = ClientRawResponse(None, response)
            return client_raw_response

    complete_feedback_notification.metadata = {"url": "/messages/serviceBound/feedback/{lockToken}"}

    def abandon_feedback_notification(
        self, lock_token, custom_headers=None, raw=False, **operation_config
    ):
        """Abandons the lock on a cloud-to-device feedback message. See
        https://docs.microsoft.com/azure/iot-hub/iot-hub-devguide-messaging for
        more information.

        :param lock_token: The lock token obtained when the cloud-to-device
         message is received.
        :type lock_token: str
        :param dict custom_headers: headers that will be added to the request
        :param bool raw: returns the direct response alongside the
         deserialized response
        :param operation_config: :ref:`Operation configuration
         overrides<msrest:optionsforoperations>`.
        :return: None or ClientRawResponse if raw=true
        :rtype: None or ~msrest.pipeline.ClientRawResponse
        :raises:
         :class:`HttpOperationError<msrest.exceptions.HttpOperationError>`
        """
        # Construct URL
        url = self.abandon_feedback_notification.metadata["url"]
        path_format_arguments = {"lockToken": self._serialize.url("lock_token", lock_token, "str")}
        url = self._client.format_url(url, **path_format_arguments)

        # Construct parameters
        query_parameters = {}
        query_parameters["api-version"] = self._serialize.query(
            "self.api_version", self.api_version, "str"
        )

        # Construct headers
        header_parameters = {}
        if custom_headers:
            header_parameters.update(custom_headers)

        # Construct and send request
        request = self._client.post(url, query_parameters, header_parameters)
        response = self._client.send(request, stream=False, **operation_config)

        if response.status_code not in [204]:
            raise HttpOperationError(self._deserialize, response)

        if raw:
            client_raw_response = ClientRawResponse(None, response)
            return client_raw_response

    abandon_feedback_notification.metadata = {
        "url": "/messages/serviceBound/feedback/{lockToken}/abandon"
    }