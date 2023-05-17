import json

from .tapioca import TapiocaInstantiator
from .exceptions import (
    AccessDenied,
    BadRequest,
    InvalidCredentials,
    NotFoundError,
    ResponseProcessException,
    ClientError,
    ServerError,
)
from .serializers import SimpleSerializer


def generate_wrapper_from_adapter(adapter_class):
    return TapiocaInstantiator(adapter_class)


class TapiocaAdapter(object):
    serializer_class = SimpleSerializer

    def __init__(self, serializer_class=None, *args, **kwargs):
        if serializer_class:
            self.serializer = serializer_class()
        else:
            self.serializer = self.get_serializer()

    def _get_to_native_method(self, method_name, value):
        if not self.serializer:
            raise NotImplementedError("This client does not have a serializer")

        def to_native_wrapper(**kwargs):
            return self._value_to_native(method_name, value, **kwargs)

        return to_native_wrapper

    def _value_to_native(self, method_name, value, **kwargs):
        return self.serializer.deserialize(method_name, value, **kwargs)

    def get_serializer(self):
        if self.serializer_class:
            return self.serializer_class()

    def get_api_root(self, api_params, **kwargs):
        return self.api_root

    def fill_resource_template_url(self, template, params):
        return template.format(**params)

    def get_request_kwargs(self, api_params, *args, **kwargs):
        serialized = self.serialize_data(kwargs.get("data"))

        kwargs.update(
            {
                "data": self.format_data_to_request(serialized),
            }
        )
        return kwargs

    def get_error_message(self, data, response=None):
        return str(data)

    def process_response(self, response):
        if 500 <= response.status_code < 600:
            raise ResponseProcessException(ServerError, None)

        data = self.response_to_native(response)

        if 400 <= response.status_code < 500:

            if response.status_code == 400:
                raise ResponseProcessException(BadRequest, data)

            if response.status_code == 401:
                raise ResponseProcessException(InvalidCredentials, data)

            if response.status_code == 403:
                raise ResponseProcessException(AccessDenied, data)

            if response.status_code == 404:
                raise ResponseProcessException(NotFoundError, data)

            if response.status_code == 500:
                raise ResponseProcessException(ServerError, data)

            raise ResponseProcessException(ClientError, data)

        return data

    def serialize_data(self, data):
        if self.serializer:
            return self.serializer.serialize(data)

        return data

    def format_data_to_request(self, data):
        raise NotImplementedError()

    def response_to_native(self, response):
        raise NotImplementedError()

    def get_iterator_list(self, response_data):
        raise NotImplementedError()

    def get_iterator_next_request_kwargs(self, iterator_request_kwargs, response_data, response):
        raise NotImplementedError()

    def is_authentication_expired(self, exception, *args, **kwargs):
        return False

    def refresh_authentication(self, api_params, *args, **kwargs):
        raise NotImplementedError()


class FormAdapterMixin(object):
    def get_request_kwargs(self, api_params, *args, **kwargs):
        params = super().get_request_kwargs(api_params, *args, **kwargs)
        if "headers" not in params:
            params["headers"] = {}
        params["headers"]["accept"] = "*/*"
        return params

    def format_data_to_request(self, data):
        if not data:
            return
        return FormAdapterMixin.encode_multipart_formdata(data)

    def response_to_native(self, response):
        return {"text": response.text}


class JSONAdapterMixin(object):
    def get_request_kwargs(self, api_params, *args, **kwargs):
        arguments = super().get_request_kwargs(api_params, *args, **kwargs)
        if "headers" not in arguments:
            arguments["headers"] = {}
        arguments["headers"]["Content-Type"] = "application/json"
        return arguments

    def format_data_to_request(self, data):
        if data:
            return json.dumps(data)

    def response_to_native(self, response):
        if response.content.strip():
            try:
                return response.json()
            except ValueError:
                return response.content

    def get_error_message(self, data, response=None):
        if not data and response.content.strip():
            data = json.loads(response.content.decode("utf-8"))

        if data:
            return data.get("error", None)
